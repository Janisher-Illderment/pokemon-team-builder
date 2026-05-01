## ADDED Requirements

### Requirement: Generar equipo de 6 alrededor de un Pokémon ancla
El sistema SHALL, dado un Pokémon ancla elegido por el usuario, seleccionar 5 Pokémon adicionales de PokéAPI que cubran los huecos ofensivos, defensivos y de roles detectados por el synergy-engine. El equipo resultante MUST incluir el Pokémon ancla en slot 1.

#### Scenario: Generación exitosa
- **WHEN** el usuario introduce "Garchomp" como Pokémon ancla
- **THEN** el sistema retorna un equipo de 6 con Garchomp en slot 1 y 5 Pokémon que cubren sus debilidades (ice, fairy, dragon) y complementan su rol (sweeper físico)

#### Scenario: El ancla ya cubre varios roles
- **WHEN** el Pokémon ancla tiene stats equilibrados y cobertura amplia
- **THEN** el sistema selecciona compañeros que añadan profundidad defensiva en lugar de replicar las fortalezas existentes

### Requirement: Generar hasta 3 variantes de equipo
El sistema SHALL ofrecer entre 1 y 3 variantes de equipo distintas usando diferentes combinaciones de Pokémon para cubrir los mismos huecos, dando al usuario opciones de elección.

#### Scenario: Múltiples variantes disponibles
- **WHEN** existen varios Pokémon candidatos para cubrir el mismo hueco
- **THEN** el sistema genera 3 variantes con diferente selección en al menos 2 slots

#### Scenario: Variantes limitadas por disponibilidad
- **WHEN** los huecos son muy específicos y hay pocos candidatos válidos
- **THEN** el sistema genera las variantes posibles (mínimo 1) sin repetir equipos idénticos

### Requirement: Excluir Pokémon legendarios y pseudo-legendarios de la generación automática por defecto
El sistema SHALL excluir Pokémon legendarios, míticos y pseudo-legendarios de los 5 slots generados automáticamente, salvo que el usuario active explícitamente la opción `--allow-legendaries`. El Pokémon ancla puede ser cualquiera.

#### Scenario: Generación estándar sin legendarios
- **WHEN** el usuario lanza la herramienta sin flags adicionales
- **THEN** ninguno de los 5 Pokémon generados es legendario o mítico

#### Scenario: Modo con legendarios activado
- **WHEN** el usuario usa la flag `--allow-legendaries`
- **THEN** el sistema puede incluir legendarios en los 5 slots generados
