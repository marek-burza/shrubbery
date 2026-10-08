#!/bin/sh

ENVIRONMENT_FILE=
if [ -f .env ]; then
  ENVIRONMENT_FILE=--env-file=.env
fi

TTY=
if [ -t 0 ]; then
  TTY=-t
fi

run() {
  podman run \
    -i $TTY \
    --rm \
    --pull=always \
    -e ANTHROPIC_API_KEY \
    -e HF_TOKEN \
    --network host \
    --userns=keep-id \
    --device nvidia.com/gpu=all \
    $ENVIRONMENT_FILE \
    --shm-size=$(free -b | awk '/^Mem:/{print $2}') \
    -e PULSE_SERVER=unix:/run/user/$(id -u)/pulse/native \
    -e PIPEWIRE_REMOTE=/run/user/$(id -u)/pipewire-0 \
    -v /run/user/$(id -u)/pulse/native:/run/user/$(id -u)/pulse/native \
    -v /run/user/$(id -u)/pipewire-0:/run/user/$(id -u)/pipewire-0 \
    -v $HOME/.ssh:/home/user/.ssh \
    -v $HOME/.claude.json:/home/user/.claude.json \
    -v $HOME/.claude:/home/user/.claude \
    -v $HOME/.cache/huggingface:/home/user/.cache/huggingface \
    -v $PWD:/home/user/workspace \
    -w /home/user/workspace \
    --entrypoint /bin/bash \
    ghcr.io/marek-burza/shrubbery:latest \
    "$@"
}

if [ $# -gt 0 ]; then
  mkdir -p workspace/logs
  run -c "$*" 2>&1 | tee "workspace/logs/$(date +%Y%m%d%H%M%S).log"
else
  run
fi
