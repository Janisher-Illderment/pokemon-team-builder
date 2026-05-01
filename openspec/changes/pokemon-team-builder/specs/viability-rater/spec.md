## ADDED Requirements

### Requirement: Puntuar la viabilidad de un equipo para Doubles de Champions (0–100)
El sistema SHALL calcular una puntuación de viabilidad para cada equipo generado sobre una escala de 0 a 100, orientada al meta de **Doubles de Pokémon Champions**. Componentes:
- **Cobertura de tipos** (35 pts): ofensiva y defensiva en Doubles
- **Balance de roles** (35 pts): sweeper + soporte + flexibilidad de selección 4-de-6
- **Distribución de SPs** (15 pts): optimización de stats para cada rol
- **Item Clause y diversidad** (15 pts): variedad de ítems y calidad de los asignados

La puntuación MUST acompañarse de una explicación en lenguaje natural de los puntos fuertes y débiles.

#### Scenario: Equipo bien equilibrado para Doubles
- **WHEN** el equipo tiene cobertura ofensiva/defensiva amplia, un lead viable, un sweeper y flexibilidad de selección alta
- **THEN** la puntuación está entre 75 y 100 y la explicación destaca los puntos fuertes

#### Scenario: Equipo con vulnerabilidad crítica en Doubles
- **WHEN** el equipo no tiene soporte ni redirect y 4 Pokémon comparten debilidad al mismo tipo
- **THEN** la puntuación está por debajo de 50 y la explicación señala los problemas concretos

### Requirement: Comparar y ordenar variantes de equipo por viabilidad
El sistema SHALL, cuando se generan múltiples variantes, ordenarlas de mayor a menor puntuación y presentar la mejor como recomendación principal.

#### Scenario: Tres variantes con puntuaciones distintas
- **WHEN** el sistema genera 3 variantes con puntuaciones 82, 71 y 65
- **THEN** la variante con 82 aparece primera y está marcada como "Recomendado"

#### Scenario: Variantes con puntuación idéntica
- **WHEN** dos variantes tienen la misma puntuación
- **THEN** el sistema las presenta en cualquier orden sin marcar ninguna como favorita
