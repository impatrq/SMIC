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

5. Agregar pdf:
    Copy-Item "C:\Users\pulid\Documents\GitHub\SMIC\docs\*.pdf" "C:\Users\pulid\Documents\GitHub\SMIC\SMIC\docs\"

6. Ver cambios:
   git status

7. Agregar cambios:
   git add .

8. Hacer commit:
   git commit -m "descripcion de lo que hiciste"

9. Subir a GitHub:
   git push origin nombre-de-tu-rama