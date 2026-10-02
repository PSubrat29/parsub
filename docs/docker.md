# Docker image

The ParSub REST API is published as a ready-made Docker image, so it runs on any computer with
Docker, without installing Python or ParSub:

**`ghcr.io/psubrat29/parsub`** – [image page](https://github.com/PSubrat29/parsub/pkgs/container/parsub)

- for Intel/AMD (`linux/amd64`) and ARM (`linux/arm64`, e.g. Apple Silicon) computers
- public: no login or account needed
- built, tested and published automatically by GitHub Actions from the source code in this repository

## Quick start

```bash
docker run -d --name parsub -p 8000:8000 -v parsub-data:/data ghcr.io/psubrat29/parsub:latest
```

Open **http://localhost:8000/** in a browser: it shows the interactive API documentation, where every
endpoint can be tried out directly.

The same, with [Docker Compose](https://docs.docker.com/compose/) and the
[`compose.yaml`](https://github.com/PSubrat29/parsub/blob/master/compose.yaml) from the repository
(it uses the same `parsub-data` volume):

```bash
docker compose up -d        # start
docker compose logs -f      # follow the log
docker compose down         # stop
```

## Using the API

```bash
# is it running?
curl http://localhost:8000/health

# analyze a LaTeX file
curl -F "file=@paper.tex" -F "output_dir=paper" http://localhost:8000/upload

# run the generated computations (plots and data are written to /data/paper)
curl -X POST http://localhost:8000/run -H "Content-Type: application/json" \
  -d '{"code_path": "paper/generated_computation.py", "timeout": 900}'

# download results: any path listed in the answer of /run
curl -O http://localhost:8000/download/paper/data/summary.json
```

`/run` lists every file it produced (plots, CSV/JSON data), as paths to use with `/download`. All endpoints and their
answers are described in the [REST API section of the User Guide](user_guide.md#rest-api).

## Where the results are kept

Everything ParSub writes (generated code, `analysis.json`, plots and data) goes to `/data` inside the
container. The quick start keeps `/data` in a Docker volume called `parsub-data`: the results survive
stopping, removing and upgrading the container.

To keep them in a folder of your computer instead, mount the folder and run the container with your
own user id so that it may write there:

```bash
mkdir -p results
docker run -d --name parsub -p 8000:8000 \
  -v "$PWD/results:/data" --user "$(id -u):$(id -g)" ghcr.io/psubrat29/parsub:latest
```

## Image tags

| Tag | Contents |
|-----|----------|
| `latest` | the newest code on the `master` branch |
| `0.2.1`, `0.2`, … | a released version: `X.Y.Z` exactly, `X.Y` the newest patch of that line |
| `sha-abc1234` | the image built from one particular commit |

For reproducible work, use a version tag, e.g. `ghcr.io/psubrat29/parsub:0.2.1`.

## Configuration

| Setting | Default | Meaning |
|---------|---------|---------|
| `-p HOST_PORT:8000` | – | the port on your computer (e.g. `-p 9000:8000` for http://localhost:9000/) |
| `-v NAME_OR_FOLDER:/data` | – | where the results are kept |
| `-e PARSUB_OUTPUT_ROOT=/data` | `/data` | output root inside the container |
| `-e PARSUB_API_PORT=8000` | `8000` | port inside the container |
| `-e PARSUB_API_HOST=0.0.0.0` | `0.0.0.0` | listen address inside the container |

## Everyday commands

```bash
docker ps                                   # STATUS shows "healthy" once the API answers
docker logs -f parsub                       # follow the log
docker stop parsub && docker rm parsub      # stop and remove (the volume is kept)
docker pull ghcr.io/psubrat29/parsub:latest # get the newest image, then start it again
docker volume rm parsub-data                # delete all stored results
```

## Build the image yourself

```bash
git clone https://github.com/PSubrat29/parsub.git
cd parsub
docker build -t parsub-api .
docker run -d --name parsub -p 8000:8000 -v parsub-data:/data parsub-api
```

The [`Dockerfile`](https://github.com/PSubrat29/parsub/blob/master/Dockerfile) builds ParSub from
`src/` in a slim Python image; the container runs as an unprivileged user, has a health check and
stops cleanly on `docker stop`.

## Security

`POST /run` executes the code ParSub generated, inside the container. Only ParSub-generated scripts
in the output root can be run and all paths are confined to `/data`, but anyone who can reach the port
can use CPU time: keep port 8000 on your own computer or network (the default `-p 8000:8000` is
reachable from your network; use `-p 127.0.0.1:8000:8000` to allow only your own computer), or put it
behind a reverse proxy with authentication.
