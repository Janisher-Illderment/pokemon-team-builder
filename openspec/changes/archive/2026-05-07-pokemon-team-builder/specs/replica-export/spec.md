## ADDED Requirements

### Requirement: Exportar equipo en formato PokePaste estándar Showdown compatible con Champions
El sistema SHALL serializar el equipo seleccionado en formato **PokePaste estándar Showdown** compatible con PikaChampions y ChampTeams.gg. Formato verificado contra ambas herramientas:
- `Level: 50` explícito en cada Pokémon
- `EVs:` con valores convertidos desde SPs (1 SP = 8 EVs)
- Sin línea `IVs:` (Showdown asume 31 por defecto, igual que Champions)
- 4 moves concretos por Pokémon (genéricos por rol, Protect en slot 1)

#### Scenario: Exportación exitosa
- **WHEN** el usuario selecciona una variante de equipo y ejecuta el export
- **THEN** el sistema imprime en stdout el bloque PokePaste con los 6 Pokémon, cada uno con Level 50, EVs convertidos, nature, ability, ítem y 4 moves

#### Scenario: Formato importable en PikaChampions
- **WHEN** el texto exportado se copia en PikaChampions o ChampTeams.gg
- **THEN** la herramienta lo importa sin errores de parsing

### Requirement: Guardar el equipo exportado en un archivo
El sistema SHALL, cuando el usuario usa la flag `--output <fichero>`, guardar el texto PokePaste en el archivo indicado.

#### Scenario: Exportación a archivo
- **WHEN** el usuario ejecuta el comando con `--output team.txt`
- **THEN** el archivo `team.txt` se crea con el contenido del equipo en formato PokePaste

#### Scenario: Archivo ya existente
- **WHEN** el archivo de destino ya existe
- **THEN** el sistema pide confirmación antes de sobreescribir, o usa la flag `--force` para omitir la confirmación

### Requirement: Mostrar instrucciones para importar el equipo en Champions
El sistema SHALL mostrar tras el export un bloque de texto con los pasos para importar el equipo en Pokémon Champions vía PikaChampions o ChampTeams.gg.

#### Scenario: Instrucciones de importación mostradas
- **WHEN** el export se completa
- **THEN** el sistema imprime la URL de la herramienta recomendada y los pasos resumidos para importar el equipo al juego vía Replica Team code
