# Guía de colaboración para agentes

Este repositorio pertenece al proyecto final de Control del bicóptero de 2 grados de libertad sobre riel vertical. Leonardo y Adrián colaboran en él; ChatGPT coordina el diseño técnico y Codex implementa, verifica y propone cambios mediante pull requests (PR). Antes de editar, leer `README.md`, `docs/WIRING_AND_SAFETY.md` y los worklogs pertinentes.

## Ramas y cambios

- Trabajar en este repositorio. Partir de `main` actualizado y crear una rama propia para cada cambio. No hacer commits ni pushes directos a `main` o `feature/sensors`, ni sobrescribir trabajo ajeno. Inspeccionar ramas de otros en modo lectura o en un worktree separado y desacoplado.
- Mantener los cambios acotados al objetivo. Usar commits Conventional Commits (`docs:`, `feat:`, `fix:`, `test:`, `chore:`). Abrir un PR hacia `main` con alcance, riesgos y evidencia de verificación. No fusionar el PR sin aprobación del equipo.
- Si un cambio afecta interfaces de sensores, control, telemetría o pinout, actualizar la documentación y el worklog correspondiente; coordinar con el equipo antes de alterar contratos compartidos.

## Seguridad física y de firmware

- Las tareas de software y revisión no autorizan energizar ESC o motores, instalar hélices, flashear la placa ni ejecutar pruebas físicas. Para una prueba de hardware, obtener autorización explícita y seguir `docs/WIRING_AND_SAFETY.md`: GND común verificado, ESP32 alimentado solo por USB, LiPo 2S solo en la etapa de potencia y pruebas iniciales sin hélices.
- Preservar el arranque desarmado (`ControlCommand.armed = false`) y los valores de comando iniciales `PWM_MIN_US = 1000`. En `main` no hay salida PWM conectada; en `feature/sensors` los pines ESC se fijan en `LOW`, que **no equivale** a generar pulsos PWM de 1000 µs. No describir una salida PWM mínima como probada físicamente.
- Respetar los contratos de `firmware/include/config.h`: `PWM_SAFE_MAX_US = 1350`, `PWM_ABS_LIMIT_US = 1500`, corte angular `55°`, riel `0–230 mm` y watchdog `250 ms`. Esos valores están declarados, pero el control, los cortes y el watchdog aún no están implementados. No armar ni habilitar PWM hasta implementar y verificar las protecciones con el procedimiento aprobado por el equipo.
- Ante sensor ausente, lectura inválida, comunicación vencida o estado fuera de límites, diseñar un comportamiento de fallo seguro y desarmado. No convertir una marca `*_ok` o un valor previo conservado en evidencia de una medición fresca sin comprobarlo.

## Verificación y evidencia

- Para compilar sin cargar firmware: `pio run -d firmware`. Para el host, desde `host/`: `python -m pip install -e .` y `python -m pytest -q`. Usar Python `>=3.11`. No ejecutar `pio run -t upload`, monitor serie, calibración de ESC ni pruebas con motores como parte de la verificación automática.
- Correr las verificaciones disponibles que correspondan a cada cambio. Reportar el comando, la revisión o rama, el resultado y cualquier limitación. `PASS` significa que la verificación indicada se ejecutó y terminó correctamente; `PARTIAL`, que solo se verificó una parte; `BLOCKED`, que no pudo ejecutarse o falta evidencia indispensable. Nunca trasladar resultados de un worklog anterior como si fueran pruebas propias.
- Diferenciar compilación y pruebas de software de validación física. Una compilación correcta no demuestra dirección de ejes, unidades, frecuencia de muestreo efectiva, distancias, respuesta ante fallos ni seguridad de motores. Registrar en el PR las comprobaciones de hardware pendientes para revisión humana.
