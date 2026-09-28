FROM golang:1.26@sha256:6c2a5538f964f1c82f97ad14988bf05de100d922d159d0e398b54c7b0ca0c6c9 AS build
WORKDIR /src
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 go build -mod=readonly -o /gateway .
FROM debian:bookworm-slim
RUN useradd --uid 10001 --create-home gateway
COPY --from=build /gateway /usr/local/bin/gateway
USER gateway
EXPOSE 8080
ENTRYPOINT ["/usr/local/bin/gateway"]
