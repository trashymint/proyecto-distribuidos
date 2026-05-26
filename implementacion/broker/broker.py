import zmq

context = zmq.Context()

frontend = context.socket(zmq.SUB)
frontend.bind("tcp://*:5555")
frontend.setsockopt_string(zmq.SUBSCRIBE, "")

backend = context.socket(zmq.PUB)
backend.bind("tcp://*:5556")

print("Broker corriendo...")

while True:
	mensaje = frontend.recv()
	print("Broker recibio datos")
	backend.send(mensaje)


