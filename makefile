.PHONY: client server

SERVER_PORT=8000
CLIENT_PORT=10000

client-local:
	python .\src\client.py localhost $(SERVER_PORT) 

server-local:
	python .\src\server.py localhost $(SERVER_PORT)

server-to:
	python .\src\server.py localhost $(port) localhost $(SERVER_PORT)