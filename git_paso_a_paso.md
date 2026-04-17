# Flujo de trabajo Git - SMIC

## Al abrir VS Code

1. Activar entorno virtual:
   venv\Scripts\activate

2. Actualizar main:
   git checkout main
   git pull origin main

3. Ir a tu rama:
   git checkout nombre-de-tu-rama

4. Traer cambios de main:
   git rebase main

## Al terminar de trabajar

5. Ver cambios:
   git status

6. Agregar cambios:
   git add .

7. Hacer commit:
   git commit -m "descripcion de lo que hiciste"

8. Subir a GitHub:
   git push origin nombre-de-tu-rama