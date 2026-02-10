import socket
import threading
import argparse

def handle_echo(path: str) -> str:
    message = path[len("/echo/"):]
    return f"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nContent-Length: {len(message)}\r\n\r\n{message}"

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

def handle_files(path: str, directory: str) -> str:
    filename = path[len("/files/"):]
    full_path = f"{directory}/{filename}"
    try:
        with open(full_path, "r") as f:
            content = f.read()
        return f"HTTP/1.1 200 OK\r\nContent-Type: application/octet-stream\r\nContent-Length: {len(content)}\r\n\r\n{content}"
    except FileNotFoundError:
        return "HTTP/1.1 404 Not Found\r\n\r\n"

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

            method, path, protocol = extract_request_info_from_request(request)
            headers = extract_headers_from_request(request)
            body = extract_body_from_request(request)
            print(
                "\n".join(
                    [
                        f"Requested method: {method}",
                        f"Requested path: {path}",
                        f"Requested protocol: {protocol}",
                        f"Requested headers: {headers}",
                        f"Requested body: {body}",
                    ]
                )
            )

            if path.startswith("/echo/"):
                response = handle_echo(path)
            elif path == "/user-agent":
                user_agent_header = headers.get("User-Agent", "Unknown")
                response = f"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nContent-Length: {len(user_agent_header)}\r\n\r\n{user_agent_header}"
            elif path.startswith("/files/"):
                response = handle_files(path, directory)
            elif path == "/":
                response = "HTTP/1.1 200 OK\r\n\r\n"
            else:
                response = "HTTP/1.1 404 Not Found\r\n\r\n"

            conn.sendall(response.encode("utf-8"))
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
