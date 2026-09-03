"""SamanTools.ui — capa de interfaz y carga visible de SamanTools V2.

Solo esta capa puede importar nuke/PySide (siempre en wrappers finos o
funciones llamadas desde Nuke); ``SamanTools.core`` permanece puro. El
inyector de entorno (``injector.py``) es el primer habitante: sus funciones
de ensamblado son puras y no importan nuke a nivel de modulo.
"""