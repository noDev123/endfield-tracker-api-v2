# from http.server import HTTPServer, BaseHTTPRequestHandler
#
#
# class Handler(BaseHTTPRequestHandler):
#     def do_GET(self):
#         try:
#             with open('docs/stats.json', 'r', encoding='utf-8') as f:
#                 body = f.read().encode()
#             self.send_response(200)
#             self.send_header('Content-Type', 'application/json')
#             self.end_headers()
#             self.wfile.write(body)
#         except FileNotFoundError:
#             self.send_response(404)
#             self.end_headers()
#             self.wfile.write(b'Run scraper.py first')
#
#     def log_message(self, format, *args):
#         print(f"{self.address_string()} - {format % args}")
#
#
# if __name__ == '__main__':
#     print("Running at http://localhost:8000")
#     HTTPServer(('', 8000), Handler).serve_forever()
