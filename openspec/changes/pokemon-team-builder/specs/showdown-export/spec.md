## ADDED Requirements

### Requirement: Exportar equipo en formato Pokémon Showdown
El sistema SHALL serializar el equipo seleccionado al formato de texto de Pokémon Showdown (nombre @ ítem / Ability / EVs / Nature / Moves), listo para copiar e importar directamente en el teambuilder de Showdown. En v1, el ítem, ability, EVs, nature y moves se rellena con valores genéricos viables para el rol del Pokémon.

#### Scenario: Exportación exitosa
- **WHEN** el usuario selecciona una variante de equipo y ejecuta el export
- **THEN** el sistema imprime en stdout el bloque de texto Showdown completo con los 6 Pokémon

#### Scenario: Formato correcto para importación
- **WHEN** el texto exportado se copia al teambuilder de Pokémon Showdown
- **THEN** Showdown lo importa sin errores de parsing (formato válido)

### Requirement: Guardar el equipo exportado en un archivo
El sistema SHALL, cuando el usuario usa la flag `--output <fichero>`, guardar el texto Showdown en el archivo indicado en lugar de (o además de) imprimirlo en stdout.

#### Scenario: Exportación a archivo
- **WHEN** el usuario ejecuta el comando con `--output team.txt`
- **THEN** el archivo `team.txt` se crea con el contenido del equipo en formato Showdown

#### Scenario: Archivo ya existente
- **WHEN** el archivo de destino ya existe
- **THEN** el sistema pide confirmación antes de sobreescribir, o usa la flag `--force` para saltarse la confirmación
