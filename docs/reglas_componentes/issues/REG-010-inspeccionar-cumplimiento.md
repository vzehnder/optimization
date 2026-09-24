# REG-010: Inspeccionar cumplimiento y fallos de las reglas en resultados

Status: Done
Type: AFK
Triage: ready-for-agent
Source: [Plan](../plan.md), sección 9.
User stories covered: HU-10.

## What to build

Agregar a los resultados internos una vista por regla que compare las filas
congeladas con la solución: valores de ambos lados, margen o residuo, unidad,
tolerancia y períodos afectados. Para corridas fallidas, distinguir errores
de código/datos, timeout e infactibilidad y permitir volver a la regla pertinente.
La explicación se reconstruye desde el snapshot y resultados de esa corrida.

## Acceptance criteria

- [x] Cada fila evaluada se atribuye a definición/revisión, instancia, componentes y período/ventana; no usa el código o alias actuales para interpretar historia.
- [x] Desigualdades muestran margen con convención documentada y las igualdades residuo; se registran tolerancias absolutas/relativas y unidades originales.
- [x] La vista filtra reglas y períodos, pagina detalles y grafica muestras claramente identificadas, sin perder filas ni limitar la comprobación al gráfico.
- [x] El estado distingue solución óptima, solución factible disponible y ausencia de solución primal; no inventa valores cuando el solver no los entrega.
- [x] Contradicciones simples enlazan reglas/períodos identificados; una infactibilidad general muestra evidencia disponible sin afirmar causa única ni un IIS inexistente.
- [x] Errores de compilación, capacidad, timeout, cancelación y solve mantienen categorías estables y acciones concretas; no se presentan todos como «modelo infactible».
- [x] Los resultados derivados de cumplimiento se pueden reconstruir desde IR y resultados congelados, sin volver a ejecutar Python.
- [x] El detalle técnico es solo interno; payloads de portal/consola no filtran código, IR, trazas ni identificadores internos por incorporar este informe.

## Demonstration and validation

Mostrar un máximo vinculante, otro con holgura y una igualdad. Resolver un caso
incompatible y comprobar la explicación limitada a la evidencia real. Editar
la regla actual y reconstruir el informe histórico con el mismo resultado.
Verificar tolerancias/escalas, ausencia de primal y paginación mediante API/UI.

## Blocked by

- [REG-004](REG-004-relacionar-componentes-hidraulicos.md).

## Implementación y fronteras TDD (2026-09-24)

Se reutilizan las fronteras confirmadas en REG-008/009: HTTP autenticado sobre
SQLite/PostgreSQL, OCI real, React/navegador y contratos públicos Julia. Los ciclos
rojo → verde cubren evaluación afín, tolerancias, estados primales, paginación,
atribución histórica, diagnósticos y contradicciones anteriores al solve.

`GET /api/runs/{id}/rule-compliance` reconstruye el informe `rule_compliance.v1`
desde `scenario_versions.system_case_json`, `summary.json` y `asset_dispatch.csv`.
No ejecuta Python, consulta el código actual ni depende del índice reconstruible
de resultados. La UI permite reconstruir, filtrar por instancia y período,
consultar filas paginadas y graficar hasta 100 muestras identificadas por unidad.
Los contadores siempre evalúan el conjunto completo, incluso al filtrar.

La IR conserva una expresión normalizada: izquierda = suma de términos y derecha
= −constante. Para `<=`, margen = derecha − izquierda; para `>=`, margen = izquierda
− derecha. Para `==`, residuo = izquierda − derecha. En la unidad original de la
fila se usa `tolerancia = 1e-7 + 1e-7 × max(abs(izquierda), abs(derecha))`.
Una desigualdad cumple con margen >= −tolerancia y una igualdad con
abs(residuo) <= tolerancia. Es la tolerancia del informe, no la configuración
interna de factibilidad de HiGHS. El informe registra ambas tolerancias y su versión.

Julia registra `primal_status` además de `termination_status`. Los archivos
históricos exitosos sin ese campo siguen disponibles; si no son óptimos, no se
afirma factibilidad certificada. Valores ausentes, no finitos o duplicados quedan
sin evaluar. Una corrida sin primal conserva constantes y procedencia, sin
inventar valores de decisión. Los errores generales de infactibilidad no prometen
una causa única ni IIS. Las cotas contradictorias identifican sus filas y enlaces,
incluido el rechazo conjunto antes de encolar; las pruebas de Python fallidas
incluyen categoría y acción correctiva.

El informe se consulta por una ruta interna independiente. No se añade a los
payloads compartidos de resultados, publicaciones, portal o consola. No hay
migraciones nuevas, cambios al SDK/imagen OCI ni modificaciones a las restricciones
matemáticas del solver. Se amplían los metadatos de éxito/error de Julia.

## Evidencia disponible

- 36 pruebas HTTP nuevas aprobadas, 18 sobre cada motor SQLite/PostgreSQL,
  incluyendo OCI real para compilación y contradicciones conjuntas.
- 104 pruebas React distintas aprobadas: 103 en la regresión inicial y una
  adicional que retira datos técnicos tras perder autorización al reconstruir.
- Chromium con API, OCI y Julia reales: 40 restricciones evaluadas, límite
  vinculante, holgura de 5 m³/s, igualdad, páginas de 25/15 filas y filtro de
  10 filas por período. Editar el código y nombre vigentes conserva el informe.
  La incompatibilidad entre caudal y conservación de agua produce `INFEASIBLE`,
  44 filas sin evaluar y enlaces al contexto. Las contradicciones simples se
  rechazan antes de crear otra corrida y permiten navegar a sus reglas.
- Capturas `frontend/test-results/reg010-compliance.png` y
  `frontend/test-results/reg010-no-primal.png` inspeccionadas visualmente.
- Regresión de corridas, resultados, portal, consola y validación web: 62 pruebas
  distintas aprobadas. Dos pruebas Julia de esa tanda requirieron repetir fuera
  del sandbox de archivos; la repetición de sus cinco pruebas pasó.

- 64 pruebas de regresión con OCI de REG-002/003/004/005/006/008/009 aprobadas.
- 586 comprobaciones Julia aprobadas: 4 nuevas de estado primal/error,
  50 de reglas y 532 de la suite general del optimizador.
- OpenAPI regenerado y `api:check`, build/TypeScript, ESLint completo, Prettier
  de archivos modificados, compilación Python y `git diff --check` aprobados.

CI queda configurado para incluir esta entrega; no se ejecutó CI remoto ni se
modificaron datos de proyectos reales. La siguiente entrega por orden es REG-011.
