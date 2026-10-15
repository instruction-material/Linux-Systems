"""Complete equipment for observing owned, loopback-only Linux services."""
import argparse
import datetime
import json
import os
import platform
import re
import shutil
import signal
import socket
import struct
import subprocess
import sys
import tempfile
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from socketserver import TCPServer

ADDRESSES = ("127.0.0.1", "127.0.0.2")


def port(value):
    number = int(value)
    if not 1 <= number <= 65535:
        raise argparse.ArgumentTypeError("use a port from 1 through 65535")
    return number


def command(argv, records):
    executable = shutil.which(argv[0])
    if not executable:
        raise RuntimeError("missing lab tool: " + argv[0])
    start = time.time()
    child = subprocess.Popen([executable, *argv[1:]], stdin=subprocess.DEVNULL,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             env=dict(os.environ, LC_ALL="C"), start_new_session=True)
    record = {"parentTaskId": os.environ.get("CLASSES_FAMILY_TASK_ID", "linux-network-investigation"),
                  "parentPid": os.getpid(), "cwd": str(Path.cwd()), "command": argv,
                  "pid": child.pid, "startTime": start, "timeoutSeconds": 8}
    cleanup = "owned query exited and reaped"
    try:
        stdout, stderr = child.communicate(timeout=8)
    except BaseException:
        cleanup = "owned query group stopped after interruption or timeout"
        os.killpg(child.pid, signal.SIGTERM)
        try:
            child.communicate(timeout=2)
        except subprocess.TimeoutExpired:
            os.killpg(child.pid, signal.SIGKILL)
            child.communicate()
        raise
    finally:
        record.update(endTime=time.time(), exitCode=child.returncode,
                      childProcessGroupCleanup=cleanup)
        records.append(record)
    record.update(stdout=stdout.decode(), stderr=stderr.decode())
    return record


def required(argv, records):
    result = command(argv, records)
    if result["exitCode"] != 0:
        raise RuntimeError("observation failed: " + " ".join(argv) + ": " + result["stderr"].strip())
    return result["stdout"]


def snapshot(address, records):
    return {"interface": json.loads(required(["ip", "-j", "address", "show", "dev", "lo"], records)),
                "mainRoutes": json.loads(required(["ip", "-j", "route", "show", "table", "main"], records)),
                "selectedRoute": json.loads(required(["ip", "-j", "route", "get", address], records))}


def listeners(number, records, udp=False):
    return required(["ss", "-H", "-lunp" if udp else "-ltnp", "sport = :" + str(number)], records)


def http_probe(address, number, path, records, hostname=None):
    assert address in ADDRESSES
    argv = ["curl", "--noproxy", "*", "--silent", "--show-error", "--fail-with-body",
            "--connect-timeout", "1", "--max-time", "2", "--write-out", "\n%{http_code}"]
    if hostname:
        assert hostname == "lab.invalid"
        argv += ["--resolve", f"{hostname}:{number}:{address}"]
    argv += [f"http://{hostname or address}:{number}{path}"]
    observed = command(argv, records)
    body, separator, status = observed["stdout"].rpartition("\n")
    if not separator or not re.fullmatch(r"\d{3}", status):
        raise RuntimeError("curl did not return its HTTP status observation")
    if observed["exitCode"] not in (0, 7, 22, 28):
        raise RuntimeError("curl observation could not be completed: " + observed["stderr"].strip())
    return {"address": address, "port": number, "path": path, "curlStatus": observed["exitCode"],
                "httpStatus": int(status), "body": body, "stderr": observed["stderr"]}


def save_report(path, report):
    """Publish a complete private record without replacing earlier evidence."""
    payload = (json.dumps(report, indent=2) + "\n").encode()
    descriptor, temporary = tempfile.mkstemp(prefix=".network-report-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, path, follow_symlinks=False)
    finally:
        Path(temporary).unlink(missing_ok=True)


class LabHttp(HTTPServer):
    allow_reuse_address = False

    def server_bind(self):
        # Literal loopback addresses need no host reverse-DNS lookup.
        TCPServer.server_bind(self)
        self.server_name = "lab.invalid"
        self.server_port = self.server_address[1]


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            status = 200 if self.server.lab_mode == "ready" else 503
            label = self.server.lab_mode
        else:
            status, label = 404, "missing"
        body = f"{label} pid={os.getpid()}\n".encode()
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, _format, *_arguments):
        pass


def service_event(event, protocol, address, number, started):
    return {"event": event, "parentTaskId": os.environ.get("CLASSES_FAMILY_TASK_ID", "linux-network-service"),
                "parentPid": os.getppid(), "cwd": str(Path.cwd()), "command": sys.argv,
                "pid": os.getpid(), "protocol": protocol, "address": address, "port": number,
                "startTime": started, "timeoutSeconds": None}


def serve_http(args):
    started = time.time()
    with LabHttp((args.bind, 0), Handler) as server:
        server.lab_mode = args.mode
        number = server.server_port
        print(json.dumps(service_event("ready", "tcp", args.bind, number, started)), flush=True)
        try:
            server.serve_forever(poll_interval=0.1)
        except KeyboardInterrupt:
            pass
    end = service_event("end", "tcp", args.bind, number, started)
    end.update(endTime=time.time(), exitCode=0, childProcessGroupCleanup="foreground owned listener closed")
    print(json.dumps(end), file=sys.stderr, flush=True)


def dns_response(query, mode):
    """Restricted RFC 1035 fixture: one ordinary IN/A question, no EDNS/TCP."""
    if len(query) < 17 or len(query) > 512:
        return None
    identity, flags, questions, answers, authorities, additional = struct.unpack("!6H", query[:12])
    if flags & 0xF800 or (questions, answers, authorities, additional) != (1, 0, 0, 0):
        return None
    offset, labels = 12, []
    while offset < len(query):
        size = query[offset]
        offset += 1
        if size == 0:
            break
        if size > 63 or offset + size > len(query):
            return None
        labels.append(query[offset:offset + size].lower())
        offset += size
    else:
        return None
    if offset + 4 != len(query) or offset > 267:
        return None
    kind, family = struct.unpack("!HH", query[offset:])
    name = b".".join(labels)
    found = name == b"lab.invalid" and kind == family == 1 and mode != "missing"
    code = 0 if found else (3 if kind == family == 1 else 4)
    header = struct.pack("!6H", identity, 0x8400 | (flags & 0x0100) | code, 1, int(found), 0, 0)
    answer = b""
    if found:
        address = "127.0.0.1" if mode == "ready" else "127.0.0.2"
        answer = b"\xc0\x0c" + struct.pack("!HHIH", 1, 1, 0, 4) + socket.inet_aton(address)
    return header + query[12:] + answer


def serve_dns(args):
    started = time.time()
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as server:
        server.bind(("127.0.0.1", 0))
        server.settimeout(0.2)
        number = server.getsockname()[1]
        print(json.dumps(service_event("ready", "udp", "127.0.0.1", number, started)), flush=True)
        try:
            while True:
                try:
                    query, sender = server.recvfrom(512)
                except TimeoutError:
                    continue
                answer = dns_response(query, args.answer)
                if answer is not None:
                    server.sendto(answer, sender)
        except KeyboardInterrupt:
            pass
    end = service_event("end", "udp", "127.0.0.1", number, started)
    end.update(endTime=time.time(), exitCode=0, childProcessGroupCleanup="foreground owned DNS socket closed")
    print(json.dumps(end), file=sys.stderr, flush=True)


def inspect(args, kind):
    if args.report.exists() or args.report.is_symlink():
        raise RuntimeError("preserve the earlier report; choose a new --report filename")
    records = []
    result = {"schemaVersion": 1, "kind": kind, "platform": platform.system(), "uid": os.geteuid(),
                  "capturedAt": datetime.datetime.now(datetime.UTC).isoformat(),
                  "learnerWorksheetCompletionInferred": False, "commands": records}
    if kind == "resolver":
        result.update(snapshot("127.0.0.1", records))
        result["dnsListener"] = listeners(args.dns_port, records, udp=True)
        result["httpListener"] = listeners(args.http_port, records)
        output = required(["dig", "-r", "@127.0.0.1", "-p", str(args.dns_port), "lab.invalid.", "A",
                           "+time=1", "+tries=1", "+noedns", "+norecurse", "+notcp", "+nosearch"], records)
        status = re.search(r"status: (NOERROR|NXDOMAIN),", output)
        addresses = re.findall(r"^lab\.invalid\.\s+\d+\s+IN\s+A\s+(127\.0\.0\.[12])\s*$", output, re.MULTILINE)
        if not status or (status[1] == "NOERROR" and len(addresses) != 1) or (status[1] == "NXDOMAIN" and addresses):
            raise RuntimeError("the fixture did not supply one expected answer or NXDOMAIN")
        result["dns"] = {"status": status[1], "answers": addresses, "raw": output}
        result["selectedAddressRequest"] = http_probe(addresses[0], args.http_port, "/health", records, "lab.invalid") if addresses else None
        result["explicitBypassRequest"] = http_probe("127.0.0.1", args.http_port, "/health", records, "lab.invalid")
        result["bypassRepairsSystemResolver"] = False
    else:
        result.update(snapshot(args.address, records))
        result["listeners"] = listeners(args.port, records)
        result["icmp"] = command(["ping", "-n", "-c", "1", "-W", "1", args.address], records)
        result["http"] = http_probe(args.address, args.port, args.path, records)
    save_report(args.report, result)
    print(f"Saved observations to {args.report}; complete the separate notes from the actual evidence.")


def main(kind):
    parser = argparse.ArgumentParser(description="Observe only the supplied loopback lab services.")
    actions = parser.add_subparsers(dest="action", required=True)
    serve = actions.add_parser("serve", help="run the owned HTTP listener in this terminal until Ctrl-C")
    serve.add_argument("--bind", choices=ADDRESSES, default="127.0.0.1")
    serve.add_argument("--mode", choices=("ready", "unavailable"), default="ready")
    if kind == "resolver":
        dns = actions.add_parser("dns", help="run the owned UDP DNS fixture in this terminal until Ctrl-C")
        dns.add_argument("--answer", choices=("ready", "wrong", "missing"), default="ready")
    collect = actions.add_parser("inspect", help="save actual tool observations without completing the worksheet")
    collect.add_argument("--report", type=Path, required=True)
    if kind == "resolver":
        collect.add_argument("--dns-port", type=port, required=True)
        collect.add_argument("--http-port", type=port, required=True)
    else:
        collect.add_argument("--port", type=port, required=True)
        collect.add_argument("--address", choices=ADDRESSES, default="127.0.0.1")
        collect.add_argument("--path", choices=("/health", "/missing"), default="/health")
    args = parser.parse_args()
    if platform.system() != "Linux" or os.geteuid() == 0:
        parser.error("use an ordinary account in the documented Linux lab")
    def interrupted(_number, _frame):
        raise KeyboardInterrupt()
    signal.signal(signal.SIGTERM, interrupted)
    try:
        if args.action == "serve":
            serve_http(args)
        elif args.action == "dns":
            serve_dns(args)
        else:
            inspect(args, kind)
    except KeyboardInterrupt:
        return 130
    except (OSError, RuntimeError, ValueError) as error:
        print("Lab failed: " + str(error), file=sys.stderr)
        return 1
    return 0
