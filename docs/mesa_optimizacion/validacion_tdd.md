# Validación de la mesa con TDD

Estado: interfaces de prueba confirmadas el 2026-10-20; no se han escrito pruebas de producto ni iniciado
la implementación en este trabajo de planificación.

Habilidad solicitada: [TDD del repositorio](../../.agents/skills/tdd/SKILL.md).
Apoyo: [pruebas](../../.agents/skills/tdd/tests.md) y
[mocks](../../.agents/skills/tdd/mocking.md).

## Interfaces públicas acordadas

La habilidad indica: **“Test only at pre-agreed seams.”** El usuario confirmó
explícitamente las interfaces siguientes el 2026-10-20. El acuerdo está registrado
en la primera entrega. No hace falta solicitarlo de nuevo para este alcance;
una interfaz adicional requiere un acuerdo explícito.

| Interfaz | Qué permite observar | Herramienta existente |
| --- | --- | --- |
| S1 · Interfaz de usuario en navegador | Pestañas, configuración, edición, ejecución, comparación, accesibilidad y disposición visible. | Playwright. |
| S2 · API HTTP pública | Persistir/recargar, permisos, revisiones, rangos, materialización, estado y resultados. | Suite Python/API existente y base aislada de prueba. |
| S3 · Entrada/salida pública del motor | Validez del contrato, resultados y balances de un caso mínimo. Solo si una entrega cambia el motor o el formato ejecutable. | CLI/contrato Julia existente y fixtures pequeños. |

Una comprobación no consulta tablas por detrás para demostrar que un guardado
funcionó. Guarda mediante la API/UI y verifica mediante una lectura posterior.
Tampoco prueba funciones privadas ni cuenta llamadas entre módulos internos.

## Ciclo por comportamiento

1. Seleccionar un criterio de aceptación y su interfaz ya acordada.
2. Escribir una prueba que describa el resultado observable para el usuario.
3. Ejecutarla y guardar evidencia del fallo por la capacidad ausente, no por una
   dependencia rota, datos inválidos o infraestructura no disponible.
4. Implementar lo mínimo para satisfacer ese comportamiento de extremo a extremo.
5. Ejecutar la misma prueba y confirmar verde, junto con regresiones pertinentes.
6. Registrar prueba, comando y evidencia en el ticket; tomar el siguiente criterio.

No escribir todas las pruebas antes de descubrir el primer recorrido funcional.
Según esta habilidad, la refactorización se reserva a la revisión posterior,
manteniendo verdes las pruebas de comportamiento.

## Capturas de referencia y qué demuestran

Se conservan dos PNG reales del prototipo y una copia del HTML:

- [Vista general antes de simular](referencias/01-mesa-general-antes.png).
- [Comparación con tres gráficos y una tabla](referencias/02-mesa-comparacion-graficos-tabla.png).
- [Cómo reproducirlas](referencias/README.md).
- [Manifest de captura](referencias/manifest.json).

Validan jerarquía, disposición de controles, cuatro paneles, pestañas, modo
gráfico/tabla y ubicación de la comparación. **No validan balances ni valores del
solver.** El demo contiene inputs y outputs ficticios e imprime una marca de
prototipo; la implementación usa datos y estados reales.

La aprobación conceptual del HTML no es una aprobación de todos los píxeles ni
de cada decisión posterior. La entrega final revisa diferencias justificadas,
por ejemplo controles de objetivo o mensajes «Sin referencia previa».

## Cómo convertirlas en regresión visual

1. Crear un fixture de presentación determinista con los mismos nombres de
   componentes, 24 intervalos del 2026-10-20 y valores conocidos. Un fixture de
   presentación puede sustituir la API pública; no sustituye las pruebas reales
   de persistencia y ejecución.
2. Fijar viewport 1440×900, DPR 1, tema claro, reloj, idioma, zona horaria,
   versión de Chromium y fuentes del entorno de pruebas. Los originales se
   capturaron en Windows, navegador en-US y zona America/Santiago.
3. Esperar fuentes, datos, fin del cálculo y ausencia de indicadores transitorios.
   No usar pausas arbitrarias en los tests; esperar estados observables.
4. Verificar en S1 que hay cuatro paneles, acciones accesibles, unidades legibles
   y controles sin solaparse. Capturar estado inicial y estado de comparación.
5. Comparar visualmente las capturas de la implementación con estos PNG de diseño.
   No exigir igualdad binaria entre el HTML de referencia y React: fuentes,
   marca de prototipo y datos reales pueden diferir justificadamente.
6. Tras aceptar la primera implementación, establecer su baseline de Playwright
   con toHaveScreenshot. Registrar el entorno y una tolerancia pequeña basada
   en renderizado repetido; no inventar un umbral amplio para hacer verde el test.
7. Revisar siempre las imágenes expected/actual/diff. No regenerar baselines
   automáticamente ante un fallo ni enmascarar paneles completos.

Los PNG de esta carpeta permanecen como fuente de diseño; los baselines
automatizados de la implementación se guardarán con sus pruebas. El rojo inicial
de TDD debe proceder de una conducta ausente o un diseño incumplido, no solamente
de que todavía no exista un archivo expected.

## Matriz de comprobaciones por entrega

| Entrega | Interfaz acordada | Ejemplo observable del primer test |
| --- | --- | --- |
| MESA-002 | S1 + S2 | Un caso con demanda expone la misma serie al alternar gráfico y tabla y al recargar. |
| MESA-003 | S1 + S2 | Guardar cuatro paneles y cambiar temporalmente a uno conserva las cuatro configuraciones. |
| MESA-004 | S1 + S2 | Un BESS sin corrida no inventa valores de descarga; demanda y renovables muestran sus entradas. |
| MESA-005 | S1 + S2 | Dos centrales con igual nombre siguen teniendo series separadas por identidad. |
| MESA-006 | S2 + S1 | Editar una entrada crea una revisión visible al recargar; una revisión concurrente produce conflicto. |
| MESA-007 | S1 + S2 | Ejecutar un caso eléctrico crea un único run con el rango validado y recupera su estado al recargar. |
| MESA-008 | S1 + S2; S3 si cambia motor | Una red hidráulica mínima produce resultados identificados por central y embalse. |
| MESA-009 | S1 + S2 | Una entrada de 10 MW congelada en un run sigue siendo 10 aunque la edición actual pase a 12. |
| MESA-010 | S1 + S2 | Volumen en hm³ nunca se empareja con caudal en m³/s; sin referencia previa no aparece una Δ falsa. |
| MESA-011 | S1 + S2; S3 si cambia motor | Un embalse creado aparece al recargar; incompleto bloquea ejecución y completo participa en el caso admitido. |
| MESA-012 | S1 + S2 | Una serie de apoyo persiste pero no afecta el run hasta tener un binding admitido. |
| MESA-013 | S1 + S2 | Recuperar un run conserva su procedencia y la exportación contiene los mismos valores que la comparación. |
| MESA-014 | S1 y evidencias previas | El recorrido completo mantiene la disposición validada y es operable con teclado y pantalla estrecha. |

Los valores esperados deben proceder de un ejemplo independiente. Por ejemplo,
la revisión de una entrada puede pasar de los literales [10, 12] a [10, 15]; la
prueba verifica esos valores por API/UI y no llama al mismo cálculo interno para
construir su expectativa. Las comprobaciones físicas usan fixtures con solución
conocida, tolerancias numéricas documentadas y los contratos públicos del motor.

## Escenarios que deben permanecer cubiertos

- Antes de la primera corrida; en cola; ejecutando; completada; fallida; recuperación
  tras pérdida de conexión o recarga.
- Entradas no editables, resultados de solo lectura, cambios pendientes y revisión
  obsoleta entre validación y ejecución.
- Serie incompleta, período sin cobertura, intervalos desiguales y cambio de hora.
- Objetos eliminados, cambio de caso, nombres duplicados, usuario sin permiso y
  selección histórica que no modifica la preparación actual.
- Tabla y gráfico sincronizados; distintas unidades; persistencia de layout y
  ausencia de scroll horizontal global a 390 px.
- Matriz 2×2 completa a 1440×900, comprobada geométricamente en el navegador además
  de revisar el screenshot.

## Ejecución futura

Usar el runner existente de cada área. Ejecutar primero la prueba específica;
ampliar a las regresiones relevantes cuando toque el contrato correspondiente.

- Frontend: npm.cmd test y npm.cmd run check.
- Navegador: npm.cmd run test:browser -- -g "mesa de optimización".
  El patrón es propuesto; hoy no existe esa suite.
- API: unittest para los módulos nuevos y los contratos afectados.
- Si cambia API: npm.cmd run api:generate y npm.cmd run api:check.
- Si cambia motor/artefactos: suite Julia del proyecto.

Estos comandos son instrucciones para la implementación posterior, no resultados
de pruebas ejecutadas ahora. El trabajo actual verifica documentos, enlaces,
dependencias y archivos de referencia.
