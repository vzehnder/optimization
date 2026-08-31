# Prototipo desechable: catálogo global y vinculación contextual

Tres variantes estructuralmente distintas, intercambiables con `?variant=`,
en una página autónoma que no toca `frontend/src`.

## Ejecutar

Desde la raíz del repositorio:

```powershell
.\.venv\Scripts\python.exe -m http.server 4174 --directory docs/wayfinder/prototypes/catalogo-global-series-genericas
```

Abrir <http://localhost:4174/?variant=A>.

## Variantes

- `A` — **Catálogo en capas**: tabla global densa, filtros a la izquierda y
  detalle de la señal en un inspector persistente. Prioriza descubrimiento y
  comparación antes de vincular.
- `B` — **Mesa de vinculación**: objeto, necesidad funcional y candidatos
  compatibles conviven en tres columnas. Prioriza entender la relación y
  soporta comenzar desde cualquiera de los dos lados.
- `C` — **Recorrido protegido**: un flujo guiado hace explícita la elección
  entre fuente genérica y serie específica, la primera carga y el impacto de
  actualizar una fuente compartida.

La barra inferior cambia de variante con clic o flechas izquierda/derecha. El
laboratorio de prototipo permite alternar el punto de entrada (`Catálogo` u
`Objeto`), el escenario funcional y los estados `normal`, `vacío`, `cargando`,
`error`, `sin permiso`, `incompatible`, `stale` y `archivado`. Todo se refleja
en la URL para poder compartir una vista exacta.

## Cobertura deliberada

- entradas, resultados y legacy separados;
- filtros, tabla signal-first, detalle dentro de su set, procedencia y revisión;
- asociaciones a objetos y bindings de variante;
- selector compatible iniciado desde catálogo u objeto;
- previsualización masiva y guardado atómico;
- comparación al reemplazar un binding;
- definición, primera carga y actualización de una serie específica por
  archivo o API, sin publicarla en el catálogo;
- impacto y consumidores afectados al revisar una genérica compartida, con la
  alternativa explícita de derivar una específica.

## Preguntas para la sesión de reacción

1. ¿La tarea principal debe empezar por explorar fuentes (`A`) o por completar
   las necesidades de un objeto (`B`)?
2. ¿El recorrido protegido de `C` debe ser el flujo principal o aparecer solo
   para cargas, reemplazos y acciones de alto impacto?
3. ¿Qué partes conviene combinar: densidad de `A`, contexto relacional de `B`
   o confirmaciones de `C`?
4. ¿La separación entre asociación de catálogo y binding de variante se
   entiende sin conocer el modelo interno?
5. ¿El aviso de impacto compartido hace suficientemente difícil publicar por
   accidente para otros consumidores?

> **PROTOTIPO DESECHABLE.** Usa datos simulados, no persiste cambios y no es
> una base de implementación.
