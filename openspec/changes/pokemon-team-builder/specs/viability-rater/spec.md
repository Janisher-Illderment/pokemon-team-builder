## ADDED Requirements

### Requirement: Puntuar la viabilidad de un equipo (0–100)
El sistema SHALL calcular una puntuación de viabilidad para cada equipo generado sobre una escala de 0 a 100, basada en tres componentes: cobertura de tipos (40 pts), balance de roles (40 pts) y media de stats base relevantes (20 pts). La puntuación MUST acompañarse de una explicación en lenguaje natural.

#### Scenario: Equipo bien equilibrado
- **WHEN** el equipo tiene cobertura ofensiva y defensiva completa, todos los roles cubiertos y stats base promedio ≥ 80
- **THEN** la puntuación está entre 75 y 100 y la explicación indica los puntos fuertes

#### Scenario: Equipo con debilidades graves
- **WHEN** el equipo tiene 4 Pokémon con debilidad a un mismo tipo y ningún soporte
- **THEN** la puntuación está por debajo de 50 y la explicación señala los problemas concretos

### Requirement: Comparar y ordenar variantes de equipo por viabilidad
El sistema SHALL, cuando se generan múltiples variantes, ordenarlas de mayor a menor puntuación y presentar la mejor variante como recomendación principal.

#### Scenario: Tres variantes con puntuaciones distintas
- **WHEN** el sistema genera 3 variantes con puntuaciones 82, 71 y 65
- **THEN** la variante con 82 aparece primera y está marcada como "Recomendado"

#### Scenario: Variantes con puntuación idéntica
- **WHEN** dos variantes tienen la misma puntuación
- **THEN** el sistema las presenta en cualquier orden sin marcar ninguna como favorita
