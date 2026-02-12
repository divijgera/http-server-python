import socket
import threading
import argparse
from dataclasses import dataclass

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

    def build_response(self, close_reponse: bool = False) -> str:
        response = f"{self.protocol} {self.status_code} {self.message}\r\n"

        if self.headers:
            for key, value in self.headers.items():
                response += f"{key}: {value}\r\n"

        if close_reponse:
            response += "Connection: close\r\n"

        response += "\r\n"

        if self.body:
            response += self.body

        return response

def extract_http_request_from_request(request: str) -> HTTPRequest:
    method, path, protocol = extract_request_info_from_request(request)
    headers = extract_headers_from_request(request)
    body = extract_body_from_request(request)
    return HTTPRequest(method, path, protocol, headers, body)


def make_response(
    *,
    status_code: int,
    message: str,
    headers: dict[str, str] | None = None,
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

def handle_echo(path: str) -> HTTPResponse:
    message = path[len("/echo/"):]
    return make_response(
        status_code=200,
        message="OK",
        headers={
            "Content-Type": "text/plain",
            "Content-Length": str(len(message)),
        },
        body=message,
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

def handle_get_files(path: str, directory: str) -> HTTPResponse:
    filename = path[len("/files/"):]
    full_path = f"{directory}/{filename}"
    try:
        with open(full_path, "r") as f:
            content = f.read()
        return make_response(
            status_code=200,
            message="OK",
            headers={
                "Content-Type": "application/octet-stream",
                "Content-Length": str(len(content)),
            },
            body=content,
        )
    except FileNotFoundError:
        return make_response(status_code=404, message="Not Found")
    
def handle_post_files(http_request: HTTPRequest, directory: str) -> HTTPResponse:
    filename = http_request.path[len("/files/"):]
    full_path = f"{directory}/{filename}"
    with open(full_path, "w") as f:
        f.write(http_request.body)

    return make_response(status_code=201, message="Created")

def handle_files(http_request: HTTPRequest, directory: str) -> HTTPResponse:
    if http_request.method == "GET":
        return handle_get_files(http_request.path, directory)
    else:
        return handle_post_files(http_request, directory)

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
                response = handle_echo(http_request.path)
            elif http_request.path == "/user-agent":
                user_agent_header = http_request.headers.get("User-Agent", "Unknown")
                response = make_response(
                    status_code=200,
                    message="OK",
                    headers={
                        "Content-Type": "text/plain",
                        "Content-Length": str(len(user_agent_header)),
                    },
                    body=user_agent_header,
                )
            elif http_request.path.startswith("/files/"):
                response = handle_files(http_request, directory)
            elif http_request.path == "/":
                response = make_response(status_code=200, message="OK")
            else:
                response = make_response(status_code=404, message="Not Found")

            conn.sendall(response.build_response(close_connection).encode("utf-8"))

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
