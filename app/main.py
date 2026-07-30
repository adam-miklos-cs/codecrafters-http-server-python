import socket
import threading
import argparse
import os
from dataclasses import dataclass, field
import gzip


@dataclass(frozen=True)
class ServerConfig:
    directory: str
    host: str = "localhost"
    port: int = 4221

    @classmethod
    def from_args(cls, args: argparse.Namespace) -> "ServerConfig":
        return cls(directory=args.directory)


@dataclass
class HTTPRequest:
    method: str
    target: str
    version: str
    headers: dict[str, str] = field(default_factory=dict)
    body: bytes = b""


@dataclass
class HTTPResponse:
    status_code: int
    status_text: str
    version: str = "HTTP/1.1"
    headers: dict[str, str] = field(default_factory=dict)
    body: bytes = b""

    def to_bytes(self) -> bytes:
        self.headers["Content-Length"] = str(len(self.body))

        lines = [f"{self.version} {self.status_code} {self.status_text}"]
        for key, value in self.headers.items():
            lines.append(f"{key}: {value}")

        head = "\r\n".join(lines) + "\r\n\r\n"
        return head.encode("utf-8") + self.body


# =====================================================================
# ROUTE HANDLERS (Returning clean HTTPResponse objects)
# =====================================================================


def handle_get(req: HTTPRequest, config: ServerConfig) -> HTTPResponse:
    if req.target == "/":
        return HTTPResponse(status_code=200, status_text="OK")

    if req.target.startswith("/echo/"):
        echo_str = req.target.split("/echo/", 1)[1]
        return HTTPResponse(
            status_code=200,
            status_text="OK",
            body=echo_str.encode("utf-8"),
            headers={"Content-Type": "text/plain"},
        )

    if req.target == "/user-agent":
        user_agent = req.headers.get("user-agent", "")
        return HTTPResponse(
            status_code=200,
            status_text="OK",
            body=user_agent.encode("utf-8"),
            headers={"Content-Type": "text/plain"},
        )

    if req.target.startswith("/files/"):
        file_name = req.target.split("/files/", 1)[1]
        full_path = os.path.join(config.directory, file_name)

        if os.path.isfile(full_path):
            with open(full_path, "rb") as file:
                return HTTPResponse(
                    status_code=200,
                    status_text="OK",
                    body=file.read(),
                    headers={"Content-Type": "application/octet-stream"},
                )

    return HTTPResponse(status_code=404, status_text="Not Found")


def handle_post(req: HTTPRequest, config: ServerConfig) -> HTTPResponse:
    if req.target.startswith("/files/"):
        file_name = req.target.split("/files/", 1)[1]
        full_path = os.path.join(config.directory, file_name)

        with open(full_path, "wb") as file:
            file.write(req.body)

        return HTTPResponse(status_code=201, status_text="Created")

    return HTTPResponse(status_code=404, status_text="Not Found")


# =====================================================================
# THE PIPELINE SWITCHBOARD
# =====================================================================


def build_response(req: HTTPRequest, config: ServerConfig) -> HTTPResponse:
    routes = {
        "GET": handle_get,
        "POST": handle_post,
    }

    if req.method in routes:
        # 1. Dispatch to the correct route handler
        response = routes[req.method](req, config)
    else:
        # 2. Handle unsupported HTTP methods
        response = HTTPResponse(status_code=405, status_text="Method Not Allowed")

    # COMPRESSION
    accept_encoding = req.headers.get("accept-encoding", "")
    supported_schemes = [scheme.strip() for scheme in accept_encoding.split(",")]

    if "gzip" in supported_schemes:
        response.body = gzip.compress(response.body)
        response.headers["Content-Encoding"] = "gzip"

    if req.headers.get("connection", "") == "close":
        response.headers["Connection"] = "close"

    return response


# =====================================================================
# PARSING & SOCKET HANDLING
# =====================================================================


def parse_headers(header_lines: list[bytes]) -> dict[str, str]:
    headers = {}
    for line in header_lines:
        if not line or b":" not in line:
            continue
        key, value = line.decode("utf-8", errors="replace").split(":", 1)
        headers[key.strip().lower()] = value.strip()
    return headers


def parse_request(raw_request_bytes: bytes) -> HTTPRequest:
    parts = raw_request_bytes.split(b"\r\n\r\n", 1)
    head = parts[0]
    body = parts[1] if len(parts) > 1 else b""

    head_lines = head.split(b"\r\n")
    if not head_lines or not head_lines[0]:
        raise ValueError("Empty or malformed HTTP request line")

    request_line_tokens = head_lines[0].decode("utf-8", errors="replace").split()
    if len(request_line_tokens) != 3:
        raise ValueError(f"Invalid HTTP request line: {head_lines[0]!r}")

    method, target, version = request_line_tokens
    headers = parse_headers(head_lines[1:])

    return HTTPRequest(method, target, version, headers, body)


def handle_request(client_socket: socket.socket, config: ServerConfig):
    try:
        DATA_LENGTH = 4096

        while True:
            raw_request_bytes = client_socket.recv(DATA_LENGTH)

            if not raw_request_bytes:
                break

            # 1. Parse raw bytes into HTTPRequest struct
            request_obj = parse_request(raw_request_bytes)

            # 2. Build and decorate the response struct
            response_obj = build_response(request_obj, config)

            # 3. Serialize to wire format and send
            client_socket.sendall(response_obj.to_bytes())

            # 4. Check if the client requested connection closure
            if request_obj.headers.get("connection", "") == "close":
                break

    except Exception as e:
        error_res = HTTPResponse(status_code=500, status_text="Internal Server Error")
        client_socket.sendall(error_res.to_bytes())
    finally:
        client_socket.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--directory", type=str, default=".")
    args = parser.parse_args()
    config = ServerConfig.from_args(args)

    server_socket = socket.create_server((config.host, config.port), reuse_port=True)

    while True:
        client_socket, client_address = server_socket.accept()
        client_thread = threading.Thread(
            target=handle_request, args=(client_socket, config)
        )
        client_thread.start()


if __name__ == "__main__":
    main()
