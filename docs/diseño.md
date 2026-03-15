# Diseño inicial - sistema de trafico distribuido

## Objetivo
Construir un sistema distribuido que simule la gestion inteligente del trafico mediante sensores y semaforos inteligentes

## Arquitectura general
El sistema se divide en 3 nodos
PC1
Sensores de trafico
Broker de comunicaion ZeroMQ

PC2
Servicio de analitica
Servicio de control de semaforos
Base de datos replica

PC3
Servicio de monitoreo
Base de datos principal

## Flujo de informacion
1. Los sensores generan eventos de trafico
2. Los eventos se envian al broker mediante ZeroMQ
3. El broker distribuye los eventos al servicio analitico
4. EL servicio de analitica detecta condiciones de trafico
5. Se envian comandos al servicio de semaforos
6. Los eventos se almacenan en la base de datos
7. El usuario puede consultar el sistema desde el servicio de monitoreo
