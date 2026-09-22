# Code inspired by:
# * https://github.com/jimfleming/numerai/blob/master/models/adversarial/model.py  # noqa: E501
# * https://machinelearningmastery.com/how-to-develop-a-generative-adversarial-network-for-a-1-dimensional-function-from-scratch-in-keras/  # noqa: E501
# * https://medium.com/@mattiaspinelli/simple-generative-adversarial-network-gans-with-keras-1fe578e44a87  # noqa: E501
# * https://github.com/eriklindernoren/Keras-GAN/blob/master/gan/gan.py  # noqa: E501
import torch
import torch.nn as nn
from tqdm import tqdm

from shrubbery.adapter import (
    LearningSchedule,
    ModelWrapper,
    TorchEstimator,
    make_scheduler,
    variance_scaling_initializer_with_fan_in,
)


class DiscriminatorNetwork(nn.Module):
    def __init__(self, feature_count: int, layer_units: list[int]) -> None:
        super().__init__()
        all_layer_units = layer_units + [1]  # Adding logits layer
        discriminator_layers: list[nn.Module] = []
        previous_units = feature_count
        for i, units in enumerate(all_layer_units):
            discriminator_layers.append(nn.Linear(previous_units, units))
            # Placing normalization before activation may:
            # * stabilize training
            # * improve activation performance (works better normalized inputs)
            # * convergence faster and get better results
            discriminator_layers.append(nn.BatchNorm1d(units))
            if i < len(all_layer_units) - 1:
                # Using ReLU (instead of sigmoid) on hidden layers may help
                # with faster and more efficient training. LeakyReLU addresses
                # the issue of "dying ReLUs" and may help maintaining non-zero
                # gradients and improve learning dynamics.
                discriminator_layers.append(nn.LeakyReLU(negative_slope=0.2))
            previous_units = units
        self.discriminator = nn.Sequential(*discriminator_layers)
        variance_scaling_initializer_with_fan_in(self)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.discriminator(x)


class GeneratorNetwork(nn.Module):
    def __init__(
        self, latent_dim: int, layer_units: list[int], feature_count: int
    ) -> None:
        super().__init__()
        all_layer_units = layer_units + [feature_count]
        generator_layers: list[nn.Module] = []
        previous_units = latent_dim
        for i, units in enumerate(all_layer_units):
            generator_layers.append(nn.Linear(previous_units, units))
            # Placing normalization before activation may:
            # * stabilize training
            # * improve activation performance (better normalized inputs)
            # * convergence faster and get better results
            generator_layers.append(nn.BatchNorm1d(units))
            # Using ReLU (instead of sigmoid) on hidden layers may help
            # with faster and more efficient training. LeakyReLU addresses
            # the issue of "dying ReLUs" and may help maintaining non-zero
            # gradients and improve learning dynamics.
            generator_layers.append(
                nn.LeakyReLU(negative_slope=0.2)
                if i < len(all_layer_units) - 1
                else nn.Sigmoid()
            )
            previous_units = units
        self.generator = nn.Sequential(*generator_layers)
        variance_scaling_initializer_with_fan_in(self)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.generator(x)


def _discrimination_auc(
    outputs: torch.Tensor, real_count: int
) -> torch.Tensor:
    """Mann-Whitney AUC of real-vs-synthetic separation from combined logits.

    ``outputs`` holds the discriminator logits for the concatenated batch, real
    rows first. Unlike d_loss - which the output BatchNorm caps into a narrow
    band around log(2) - this is invariant to logit scale, so it shows whether
    the discriminator can still separate at all. It is the quantity that tracks
    embedding quality: the embedder is the discriminator's penultimate layer,
    so an AUC decaying to 0.5 means the extracted embedding is drifting towards
    an arbitrary projection.
    """
    flat = outputs.detach().flatten()
    sorted_values, order = torch.sort(flat)
    # Midranks, so that tied logits share the average of the ranks they span.
    # Without this a fully collapsed discriminator - every logit identical,
    # which is what the output BatchNorm produces once its gamma decays to
    # zero - would score an arbitrary 0.0 or 1.0 instead of the correct 0.5.
    first = torch.searchsorted(sorted_values, sorted_values, right=False)
    last = torch.searchsorted(sorted_values, sorted_values, right=True)
    midranks = (first + last + 1).to(flat.dtype) / 2
    ranks = torch.empty_like(flat)
    ranks[order] = midranks
    fake_count = flat.numel() - real_count
    real_rank_sum = ranks[:real_count].sum()
    return (real_rank_sum - real_count * (real_count + 1) / 2) / (
        real_count * fake_count
    )


class GenerativeAdversarialNetworkEmbedder(TorchEstimator):
    def __init__(
        self,
        batch_size: int,
        epochs: int,
        latent_dim: int,
        generator_layer_units: list[int],
        discriminator_layer_units: list[int],
        learning_rate: float,
        learning_schedule: LearningSchedule | None = None,
    ) -> None:
        super().__init__(
            epochs=epochs,
            batch_size=batch_size,
            learning_rate=learning_rate,
            learning_schedule=learning_schedule,
        )
        self.latent_dim = latent_dim
        self.generator_layer_units = generator_layer_units
        self.discriminator_layer_units = discriminator_layer_units

    def train(self, x: torch.Tensor, y: torch.Tensor) -> nn.Module:
        x = x.to(self._device)
        # GAN
        feature_count = x.shape[1]
        discriminator = DiscriminatorNetwork(
            feature_count, self.discriminator_layer_units
        ).to(self._device)
        d_optimizer = torch.optim.Adam(
            discriminator.parameters(),
            lr=self.learning_rate,
            weight_decay=1e-3,
        )
        generator = GeneratorNetwork(
            self.latent_dim,
            self.generator_layer_units,
            feature_count,
        ).to(self._device)
        g_optimizer = torch.optim.Adam(
            generator.parameters(),
            lr=self.learning_rate,
            weight_decay=1e-3,
        )
        criterion = nn.BCEWithLogitsLoss()
        # Training
        rows = x.shape[0]
        d_scheduler = make_scheduler(
            d_optimizer,
            self.learning_schedule,
            self.learning_rate,
            self.epochs,
        )
        g_scheduler = make_scheduler(
            g_optimizer,
            self.learning_schedule,
            self.learning_rate,
            self.epochs,
        )
        for epoch in (progress := tqdm(range(self.epochs))):
            order = torch.randperm(rows, device=x.device)
            # Accumulated on device and synchronised once per epoch, so the
            # reported figures are epoch means rather than a single last batch.
            d_loss_total = torch.zeros((), device=self._device)
            g_loss_total = torch.zeros((), device=self._device)
            auc_total = torch.zeros((), device=self._device)
            batches = 0
            for start in range(0, rows, self.batch_size):
                x_batch = x[order[start : start + self.batch_size]]
                batch_size = x_batch.size(0)
                # Train discriminator
                discriminator.train()
                d_optimizer.zero_grad()
                g_noise = torch.randn(batch_size, self.latent_dim).to(
                    self._device
                )
                synthetic_features = generator(g_noise)
                x_combined = torch.cat(
                    [x_batch, synthetic_features.detach()], dim=0
                )
                y_combined = torch.cat(
                    [torch.ones(batch_size, 1), torch.zeros(batch_size, 1)],
                    dim=0,
                ).to(self._device)
                d_outputs = discriminator(x_combined)
                d_loss = criterion(d_outputs, y_combined)
                d_loss.backward()
                d_optimizer.step()
                # Train generator
                discriminator.eval()
                g_optimizer.zero_grad()
                d_noise = torch.randn(2 * batch_size, self.latent_dim).to(
                    self._device
                )
                fake_samples = generator(d_noise)
                fake_outputs = discriminator(fake_samples)
                y_mislabeled = torch.ones(2 * batch_size, 1).to(self._device)
                g_loss = criterion(fake_outputs, y_mislabeled)
                g_loss.backward()
                g_optimizer.step()
                d_loss_total += d_loss.detach()
                g_loss_total += g_loss.detach()
                auc_total += _discrimination_auc(d_outputs, batch_size)
                batches += 1
            if d_scheduler is not None:
                d_scheduler.step()
            if g_scheduler is not None:
                g_scheduler.step()
            progress.set_description(
                f'Training - epoch: {epoch}; '
                f'd_loss: {(d_loss_total / batches).item():.5f}; '
                f'g_loss: {(g_loss_total / batches).item():.5f}; '
                f'auc: {(auc_total / batches).item():.5f}'
            )
        # Extract embedder from discriminator (remove last 2 layers, earlier ones have 3)
        # Removes: final Linear & BatchNorm
        # Keeps: all layers up to and including the last hidden LeakyReLU
        embedder_layers = list(discriminator.discriminator.children())[:-2]
        embedder = nn.Sequential(*embedder_layers)
        return ModelWrapper(embedder)

    def module(self, input_dim: int) -> nn.Module:
        discriminator = DiscriminatorNetwork(
            input_dim, self.discriminator_layer_units
        )
        embedder_layers = list(discriminator.discriminator.children())[:-2]
        return nn.Sequential(*embedder_layers)
