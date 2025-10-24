import os
import sys
import importlib.util
from pathlib import Path

def find_py_files(root):
    py_files = []
    for dirpath, _, filenames in os.walk(root):
        for filename in filenames:
            if filename.endswith('.py') and not filename.startswith('__'):
                full_path = os.path.join(dirpath, filename)
                py_files.append(full_path)
    return py_files

def import_file(file_path, project_root):
    # Calcula el nombre del módulo relativo para importlib (e.g. app.ui.windows.dashboard_window)
    rel_path = Path(file_path).relative_to(project_root).with_suffix('')
    module_name = ".".join(rel_path.parts)
    try:
        spec = importlib.util.spec_from_file_location(module_name, file_path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        return True, None
    except Exception as e:
        return False, str(e)

def main():
    project_root = Path(__file__).parent.resolve()
    print(f"Escaneando archivos .py en: {project_root}\n")

    py_files = find_py_files(project_root)
    results = []

    for py_file in py_files:
        ok, error = import_file(py_file, project_root)
        rel_path = str(Path(py_file).relative_to(project_root))
        results.append((rel_path, ok, error))

    print("\n=== MAPA DE LA APP ===")
    print("ARCHIVOS QUE SE IMPORTAN CORRECTAMENTE:")
    for rel_path, ok, _ in results:
        if ok:
            print(f"  ✔ {rel_path}")

    print("\nARCHIVOS CON ERROR AL IMPORTAR:")
    for rel_path, ok, error in results:
        if not ok:
            print(f"  ✖ {rel_path}  [{error}]")

    print("\nTotal archivos:", len(results))
    print(f"Funcionando: {sum(ok for _, ok, _ in results)}, Con error: {sum(not ok for _, ok, _ in results)}")

if __name__ == "__main__":
    main()