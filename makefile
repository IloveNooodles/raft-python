.PHONY: client server

client-local:
	python .\src\client.py localhost 8000 localhost 

server-local:
	python .\src\server.py localhost 8000