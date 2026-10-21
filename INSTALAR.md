# Instalar GestorIA

Estas son las instrucciones que sigue tu agente cuando le pegas el mensaje de instalación del
[README](README.md#instálalo-con-tu-agente). Si prefieres hacerlo a mano, los pasos son los mismos.

> **Para el agente.** Sigue los pasos en orden. Haz todas las preguntas del paso 4 en un solo
> mensaje. **No te inventes ningún dato de la empresa**: lo que la persona no sepa se queda marcado
> como `PENDIENTE` y se lo dices al final. Si algo falla, para y cuéntale qué ha pasado, con el
> mensaje exacto; no busques atajos. Y respeta [lo que no se hace](#lo-que-no-se-hace).

## Lo que vas a dejar montado

| qué | dónde |
|---|---|
| el código y su entorno de Python | `~/GestorIA` |
| las skills, para que el agente sepa hacer de gestor | `.claude/skills/` del proyecto, o `~/.claude/skills/` si la persona lo quiere en todos |
| la carpeta con los datos de la empresa | `~/.gestoria/<empresa>/`, fuera de cualquier repositorio |
| una nota con las rutas, para las próximas sesiones | el `CLAUDE.md` del proyecto (`AGENTS.md` si usa Codex u otro agente) |
| el panel web | solo si la persona lo ha pedido |
| las tareas del cron | solo si la persona dice que sí |

## 1. Comprueba lo que hace falta

```bash
git --version
python3 --version          # tiene que ser 3.11 o más
```

Si falta git o Python es anterior a 3.11, para y dile a la persona qué tiene que instalar. No
instales nada del sistema ni uses `sudo` por tu cuenta.

GestorIA se prueba en Linux (Ubuntu, con Python de la 3.11 a la 3.14). En macOS los pasos son los
mismos. En Windows, hazlo dentro de WSL.

## 2. Descarga el código e instálalo

Con el repositorio que venga en el mensaje:

```bash
git clone <repositorio> ~/GestorIA          # si ~/GestorIA no existe
git -C ~/GestorIA pull --ff-only            # si ya existe y es un clon de GestorIA
```

Si `~/GestorIA` existe pero no es un clon de GestorIA, no lo toques: pregunta dónde instalarlo.

```bash
python3 -m venv ~/GestorIA/.venv
~/GestorIA/.venv/bin/pip install -e "$HOME/GestorIA[sede,manuales]"
~/GestorIA/.venv/bin/python -m playwright install chromium
```

Chromium (algo más de 300 MB de descarga) es el navegador con el que GestorIA usa el simulador de
Hacienda y entra en las sedes. Si Playwright avisa de que faltan librerías del sistema, pásale a la persona el comando
que propone; no lo ejecutes tú.

## 3. Comprueba que funciona, con la empresa de ejemplo

```bash
~/GestorIA/.venv/bin/gestoria --carpeta ~/GestorIA/ejemplos/sl-demo hoy
~/GestorIA/.venv/bin/gestoria --carpeta ~/GestorIA/ejemplos/sl-demo deducciones
```

`hoy` sale con el semáforo como código (0 verde, 1 amarillo, 2 rojo): eso no es un fallo. Un fallo
es el código 3. Enséñale a la persona las primeras líneas de `hoy`, para que vea qué pinta tiene.

## 4. Pregunta por la empresa, todo de una vez

Si el mensaje no decía si quiere el panel, pregúntalo también.

1. ¿Es una **SL** o es **autónomo**?
2. El **nombre** (o la razón social) y el **NIF**.
3. El **régimen de IVA**: general, o REBU si vende bienes usados. Si no lo sabe, general.
4. Los **modelos que presenta** (303, 390, 130, 111, 115, 347, 349, 200…). Si no lo sabe, pon los
   de la empresa de ejemplo de su tipo y márcalos `PENDIENTE`: con el certificado, `gestoria censo`
   dirá cuáles tiene de alta de verdad.
5. Si es una **SL**: ¿se ha creado hace poco? (el 15 % de nueva creación vale el primer ejercicio
   con beneficios y el siguiente) ¿Y cuál fue su cifra de negocios el año pasado? Si es
   **autónomo**: su cuota mensual de autónomos y su rendimiento neto del año pasado.
6. Para las **ayudas**: su provincia o su comunidad, y tres o cuatro palabras de a qué se dedica.
7. ¿Tiene **certificado digital**? Si lo tiene, solo la ruta del fichero `.p12` o `.pfx`. **La
   contraseña no se pide nunca en el chat.**
8. ¿Quiere que deje programadas las **tareas automáticas** (el cron)?

## 5. Crea su carpeta de datos

Ponle un nombre corto y sin espacios, como `~/.gestoria/bicis-lopez`.

```bash
mkdir -p ~/.gestoria/<empresa>/libros ~/.gestoria/<empresa>/banco
chmod 700 ~/.gestoria
```

- **`perfil.toml`**: copia el de `~/GestorIA/ejemplos/sl-demo/` o el de
  `~/GestorIA/ejemplos/autonomo-demo/` y pon sus datos. Quita lo que no le aplique y deja los
  comentarios que explican cada campo. Lo que no sepa, comentado con `# PENDIENTE:` y lo que falta.
- **`libros/ventas.csv`** y **`libros/compras.csv`**: solo la primera línea (la cabecera) de los del
  ejemplo de su tipo. Si te pasa sus facturas, pásalas tú a esas columnas.
- **`ajustes.toml`**: solo si sabe el saldo a compensar del último 303 presentado (su casilla [87])
  o si la empresa es nueva (`"0.00"`), y siempre con su `fuente`. Si no lo sabe, no lo crees: apunta
  que está pendiente.

Comprueba que lo lee bien:

```bash
~/GestorIA/.venv/bin/gestoria --carpeta ~/.gestoria/<empresa> revisar
~/GestorIA/.venv/bin/gestoria --carpeta ~/.gestoria/<empresa> hoy
```

### Si tiene certificado

En su `perfil.toml`:

```toml
[sede]
certificado = "~/ruta/al/certificado.p12"
clave_fichero = "~/.config/gestoria/clave_empresa.txt"
```

La contraseña la escribe la persona en su propia terminal, no en el chat. Pásale estas dos líneas
para que las pegue allí; la segunda le pide la contraseña sin enseñarla y la guarda con permisos
600:

```bash
mkdir -p ~/.config/gestoria && chmod 700 ~/.config/gestoria
(umask 077; printf "Contraseña del certificado: "; IFS= read -rs CLAVE; echo; printf %s "$CLAVE" > ~/.config/gestoria/clave_empresa.txt)
```

Si también tiene el suyo de persona física, va igual en `[sede.personal]`, con `clave_yo.txt`.
Luego comprueba el certificado, que se mira en local y sin red:

```bash
~/GestorIA/.venv/bin/gestoria --carpeta ~/.gestoria/<empresa> certificado
```

Te dice de quién es, de qué tipo es y cuándo caduca. El chequeo y el vigía sí entran en las sedes:
no los lances sin que la persona diga que sí. Ofréceselos al final.

## 6. Instala las skills

Desde la carpeta del proyecto:

```bash
~/GestorIA/.venv/bin/gestoria instalar-skills              # en este proyecto: .claude/skills/
~/GestorIA/.venv/bin/gestoria instalar-skills --global     # o en todos: ~/.claude/skills/
```

Si usa otro agente, copia las carpetas de `~/GestorIA/skills/` a donde ese agente lea sus skills.

## 7. Deja una nota para las próximas sesiones

Añade esta sección al final del `CLAUDE.md` del proyecto: créalo si no existe y, si existe, no
toques lo demás. Con Codex u otro agente, en su `AGENTS.md`.

```markdown
## GestorIA

- Órdenes: `~/GestorIA/.venv/bin/gestoria --carpeta ~/.gestoria/<empresa> <orden>`
- Datos de la empresa: `~/.gestoria/<empresa>/`. Están fuera del repositorio: no se copian aquí ni se suben.
- Antes de contestar nada fiscal, lee la skill `gestoria`.
- Panel: `gestoria web` (http://127.0.0.1:8640). Si no lo quiso: «sin panel».
- Pendiente: lo que haya quedado como PENDIENTE.
```

## 8. El panel (solo si lo ha pedido)

```bash
~/GestorIA/.venv/bin/gestoria --carpeta ~/GestorIA/ejemplos/sl-demo web --fichero
~/GestorIA/.venv/bin/gestoria --carpeta ~/.gestoria/<empresa> web --fichero
```

Cada orden deja un único HTML en `salida/web/index.html` de su carpeta y te dice dónde. Ábrelos con
`xdg-open` en Linux o con `open` en macOS: el de ejemplo, para que vea cómo queda con datos, y el
suyo, que estará casi vacío hasta que entren sus facturas.

Para el día a día, `gestoria web` sirve el panel en http://127.0.0.1:8640 y lo rehace con cada
recarga. Es un servidor que se queda esperando, así que no lo lances tú en primer plano: dile a la
persona que lo abra cuando quiera (Ctrl+C lo cierra).

Sin panel, sáltate este paso. Si algún día lo quiere, es `gestoria web`.

## 9. El cron (solo si dice que sí)

Parte de `~/GestorIA/workflows/crontab.ejemplo`: cambia las rutas por las de verdad (`G`,
`GESTORIA_CARPETA`, `F`) y pon su correo. Si no tiene certificado, quita las líneas que lo
necesitan (`vigia`, `cotejar`, `chequeo`). Si pidió el panel, añade una línea que lo rehaga cada
mañana:

```
40 8 * * *     $G web --fichero > /dev/null 2>> $GESTORIA_CARPETA/salida/errores.log
```

Enséñale las líneas antes de instalarlas y añádelas sin borrar lo que ya tenga en su cron:

```bash
(crontab -l 2>/dev/null; cat lineas_gestoria.txt) | crontab -
```

`gestoria presentar` no va nunca en el cron. Si no tiene `mail` configurado, deja que el vigía
escriba en su log y díselo.

## 10. Cuéntale cómo ha quedado

- Qué has instalado y dónde: la tabla de arriba, con sus rutas.
- Lo que ha quedado `PENDIENTE` y cómo resolverlo.
- Tres cosas para probar ya: «¿qué vence este mes?», «¿qué me puedo deducir?» y «¿hay alguna ayuda
  para mí?». Si tiene certificado, ofrécele el primer chequeo.
- Cómo se actualiza GestorIA:

  ```bash
  git -C ~/GestorIA pull --ff-only
  ~/GestorIA/.venv/bin/pip install -e "$HOME/GestorIA[sede,manuales]"
  ~/GestorIA/.venv/bin/gestoria instalar-skills        # desde el proyecto (o con --global)
  ```

## Lo que no se hace

- Durante la instalación no se presenta nada, no se abre ninguna notificación y no se entra en
  ninguna sede. El primer chequeo, cuando la persona lo pida.
- La contraseña del certificado y las cookies del banco no pasan nunca por el chat.
- Los datos de la empresa no se guardan dentro de `~/GestorIA` ni del proyecto. Si la persona los
  quiere en el proyecto, añade antes esa carpeta al `.gitignore`.
- No se hace commit ni push de nada.
- No se instala nada con `sudo`.
