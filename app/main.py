import socket
import threading
import argparse
from dataclasses import dataclass
from typing import Optional

SERVER_ACCEPTED_ENCODINGS = ["gzip"]

@dataclass
class HTTPRequest:
    method: str
    path: str
    protocol: str
    headers: dict[str, str]
    body: str

@dataclass
class HTTPResponse:
    status_code: int
    protocol: str
    headers: dict[str, str]
    body: str
    message: str

    def handle_compression(self, compression_method: str) -> str:
        return self.body

    def build_response(self) -> str:
        response = f"{self.protocol} {self.status_code} {self.message}\r\n"

        compression_method = None

        if self.headers and "Content-Encoding" in self.headers:
            compression_method = self.headers["Content-Encoding"]

        if self.headers:
            for key, value in self.headers.items():
                response += f"{key}: {value}\r\n"

        response += "\r\n"

        if self.body:
            response += self.handle_compression(self.body) if compression_method else self.body

        return response
    
def generate_response_headers(
        request_headers: Optional[dict[str, str]] = None,
        additional_headers: Optional[dict[str, str]] = None,
    ) -> dict[str, str]:
    headers = {}

    if not request_headers and not additional_headers:
        return headers
    
    if additional_headers:
        headers.update(additional_headers)
    
    if not request_headers:
        return headers
    
    for key, value in request_headers.items():
        if key == "Accept-Encoding":
            accepted_encodings = [encoding.strip() for encoding in request_headers["Accept-Encoding"].split(",")]
            for encoding in accepted_encodings:
                if encoding in SERVER_ACCEPTED_ENCODINGS:
                    headers["Content-Encoding"] = encoding
                    break
        elif key == "Connection":
            headers[key] = value
    
    return headers

def extract_http_request_from_request(request: str) -> HTTPRequest:
    method, path, protocol = extract_request_info_from_request(request)
    headers = extract_headers_from_request(request)
    body = extract_body_from_request(request)
    return HTTPRequest(method, path, protocol, headers, body)

def make_response(
    *,
    status_code: int,
    message: str,
    headers: Optional[dict[str, str]] = None,
    body: str = "",
    protocol: str = "HTTP/1.1",
) -> HTTPResponse:
    return HTTPResponse(
        status_code=status_code,
        protocol=protocol,
        headers=headers or {},
        body=body,
        message=message,
    )

def extract_request_info_from_request(request: str) -> tuple[str, str, str]:
    request_info = request.split("\r\n")[0].split(" ")
    method = request_info[0]
    path = request_info[1]
    protocol = request_info[2]
    return method, path, protocol

def extract_headers_from_request(request: str) -> dict[str, str]:
    headers = {}
    for line in request.split("\r\n")[1:]:
        if line == "":
            # An empty line indicates the end of the headers
            break
        key, value = line.split(": ", 1)
        headers[key] = value
    return headers

def extract_body_from_request(request: str) -> str:
    return request.split("\r\n\r\n", 1)[1] if "\r\n\r\n" in request else ""

def handle_echo(http_request: HTTPRequest) -> HTTPResponse:
    message = http_request.path[len("/echo/"):]
    return make_response(
        status_code=200,
        message="OK",
        headers=generate_response_headers(
            request_headers=http_request.headers,
            additional_headers={
                "Content-Type": "text/plain",
                "Content-Length": str(len(message)),
            }
        ),
        body=message,
    )

def handle_user_agent(http_request: HTTPRequest) -> HTTPResponse:
    user_agent_header = http_request.headers.get("User-Agent", "Unknown")
    return make_response(
        status_code=200,
        message="OK",
        headers=generate_response_headers(
            request_headers=http_request.headers,
            additional_headers={
                "Content-Type": "text/plain",
                "Content-Length": str(len(user_agent_header)),
            }
        ),
        body=user_agent_header,
    )

def handle_get_files(http_request: HTTPRequest, directory: str) -> HTTPResponse:
    filename = http_request.path[len("/files/"):]
    full_path = f"{directory}/{filename}"
    try:
        with open(full_path, "r") as f:
            content = f.read()
        return make_response(
            status_code=200,
            message="OK",
            headers=generate_response_headers(
                request_headers=http_request.headers,
                additional_headers={
                    "Content-Type": "application/octet-stream",
                    "Content-Length": str(len(content))
                }
            ),
            body=content,
        )
    except FileNotFoundError:
        return make_response(status_code=404, message="Not Found",headers=generate_response_headers(request_headers=http_request.headers))
    
def handle_post_files(http_request: HTTPRequest, directory: str) -> HTTPResponse:
    filename = http_request.path[len("/files/"):]
    full_path = f"{directory}/{filename}"
    with open(full_path, "w") as f:
        f.write(http_request.body)

    return make_response(status_code=201, message="Created",headers=generate_response_headers(request_headers=http_request.headers))

def handle_files(http_request: HTTPRequest, directory: str) -> HTTPResponse:
    if http_request.method == "GET":
        return handle_get_files(http_request, directory)
    else:
        return handle_post_files(http_request, directory)
    
def handle_root(http_request: HTTPRequest) -> HTTPResponse:
    return make_response(status_code=200, message="OK", headers=generate_response_headers(request_headers=http_request.headers))

def handle_client(conn: socket.socket, addr, directory: str) -> None:
    # wait for client
    print(f"Connection from {addr}")
    try:
        while True:
            request = conn.recv(4096)
            if not request:
                break
            request = request.decode("utf-8")
            print(f"Received request: {request}")

            http_request = extract_http_request_from_request(request)
            print(
                "\n".join(
                    [
                        f"Requested method: {http_request.method}",
                        f"Requested path: {http_request.path}",
                        f"Requested protocol: {http_request.protocol}",
                        f"Requested headers: {http_request.headers}",
                        f"Requested body: {http_request.body}",
                    ]
                )
            )

            close_connection = http_request.headers.get("Connection", "").lower() == "close"

            if http_request.path.startswith("/echo/"):
                response = handle_echo(http_request)
            elif http_request.path == "/user-agent":
                response = handle_user_agent(http_request)
            elif http_request.path.startswith("/files/"):
                response = handle_files(http_request, directory)
            elif http_request.path == "/":
                response = handle_root(http_request)
            else:
                response = make_response(status_code=404, message="Not Found",headers=generate_response_headers(request_headers=http_request.headers))

            conn.sendall(response.build_response().encode("utf-8"))

            if close_connection:
                break
    finally:
        conn.close()

def main(directory: str) -> None:
    with socket.create_server(("localhost", 4221), reuse_port=True) as server_socket:
        while True:
            conn, addr = server_socket.accept()
            thread = threading.Thread(target=handle_client, args=(conn, addr, directory), daemon=True)
            thread.start()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="A simple HTTP server.")
    parser.add_argument("--directory", type=str, default=".", help="The directory to serve files from.")
    args = parser.parse_args()
    main(args.directory)
