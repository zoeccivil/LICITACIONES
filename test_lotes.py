# test_lotes.py
from types import SimpleNamespace
from glicitaciones import Licitacion

def main():
    # Simulamos lotes como objetos simples con atributos
    loteA = SimpleNamespace(
        monto_base=100.0,
        monto_base_personal=110.0,
        participamos=True
    )
    loteB = SimpleNamespace(
        monto_base=200.0,
        monto_base_personal=None,  # este lote no tiene base personal
        participamos=True
    )
    loteC = SimpleNamespace(
        monto_base=150.0,
        monto_base_personal=140.0,
        participamos=False  # no participamos
    )

    # Creamos licitación ficticia con los 3 lotes
    lic = Licitacion()
    lic.lotes = [loteA, loteB, loteC]

    # Pruebas sin filtro (todos los lotes)
    print("=== TODOS LOS LOTES ===")
    print("Base oficial total:", lic.get_monto_base_total())
    print("Base personal total:", lic.get_monto_base_personal_total())
    print("Diferencia %:", lic.get_diferencia_bases_porcentual(), "%")

    # Pruebas solo con lotes participados
    print("\n=== SOLO PARTICIPADOS ===")
    print("Base oficial total:", lic.get_monto_base_total(solo_participados=True))
    print("Base personal total:", lic.get_monto_base_personal_total(solo_participados=True))
    print("Diferencia %:", lic.get_diferencia_bases_porcentual(solo_participados=True), "%")


if __name__ == "__main__":
    main()
