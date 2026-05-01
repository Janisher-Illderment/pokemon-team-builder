## ADDED Requirements

### Requirement: Exportar equipo en formato PokePaste compatible con Champions
El sistema SHALL serializar el equipo seleccionado en formato **PokePaste** compatible con PikaChampions (pikachampions.com) y ChampTeams.gg. El formato usa **Stat Points (SPs)** en lugar de EVs:
- IVs se omiten (son 31 fijos en Champions)
- EVs se reemplazan por `SPs: <stat>/<valor>` usando la distribución calculada por team-generator
- Incluye: nombre, ítem, ability, nature, SPs, moveset para los 6 Pokémon

#### Scenario: Exportación exitosa
- **WHEN** el usuario selecciona una variante de equipo y ejecuta el export
- **THEN** el sistema imprime en stdout el bloque PokePaste completo con los 6 Pokémon y sus SPs

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
