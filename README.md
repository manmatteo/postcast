# postcast
Crea dei feed RSS per i podcast de Il Post.

Comportamento predefinito:

- Controlla la pagina dei nuovi episodi
- Se un file `xml` esiste localmente, aggiunge il nuovo episodio al file `xml`
- Se non esiste, cerca tutti gli episodi del podcast e crea un nuovo file `xml`

In particolare, lo script assume che se un file `xml` esiste, contiene tutti gli episodi del podcast anteriori a quelli presenti nella pagina dei nuovi episodi.
