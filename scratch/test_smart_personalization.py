import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database import init_db, get_db_connection, get_workspace_personalization, save_workspace_personalization
from services.bank_importer import build_dynamic_smart_tags, seed_personalization_rules, load_workspace_category_rules
from app import app

def run_tests():
    init_db()
    print("1. Testing database helper save_workspace_personalization...")
    test_ws_id = 2
    pers = save_workspace_personalization(test_ws_id, {
        "children_names": "Luciano, Matteo",
        "pets_names": "Luna",
        "housing_type": "MUTUO",
        "mortgage_bank": "Intesa Sanpaolo",
        "vehicle_types": "Auto, Telepass",
        "employment_type": "DIPENDENTE",
        "has_pension_fund": 1,
        "onboarding_completed": 1
    })
    assert pers["children_names"] == "Luciano, Matteo"
    assert pers["pets_names"] == "Luna"
    assert pers["mortgage_bank"] == "Intesa Sanpaolo"
    print("Database persistence OK!")

    print("2. Testing seed_personalization_rules...")
    patterns = seed_personalization_rules(test_ws_id, pers)
    assert "ORIGINAL MARINES" in patterns
    assert "VILLA BEBE" in patterns
    assert "ARCAPLANET" in patterns
    assert "MUTUO INTESA SANPAOLO" in patterns

    rules = load_workspace_category_rules(test_ws_id)
    rule_map = {r['pattern']: r for r in rules}
    assert "#luciano" in rule_map["ORIGINAL MARINES"]["tags"]
    assert "#matteo" in rule_map["ORIGINAL MARINES"]["tags"]
    assert "#luna" in rule_map["ARCAPLANET"]["tags"]
    print("Rule generation and tagging OK!")

    print("3. Testing build_dynamic_smart_tags...")
    dyn_tags = build_dynamic_smart_tags(pers)
    shopping_codes = [t["code"] for t in dyn_tags["Shopping & Abbigliamento"]]
    assert "#luciano" in shopping_codes
    assert "#matteo" in shopping_codes
    
    salute_codes = [t["code"] for t in dyn_tags["Salute & Benessere"]]
    assert "#luna" in salute_codes
    
    casa_codes = [t["code"] for t in dyn_tags["Casa & Immobili"]]
    assert "#mutuo" in casa_codes
    print("Dynamic Smart Tags enrichment OK!")

    print("4. Testing API Endpoints & Template Rendering...")
    with app.test_client() as c:
        with c.session_transaction() as sess:
            sess['user_id'] = 2
            sess['workspace_id'] = test_ws_id
            sess['role'] = 'USER'

        # Test GET /api/personalization
        res_get = c.get('/api/personalization')
        assert res_get.status_code == 200
        json_get = res_get.get_json()
        assert json_get["success"] is True
        assert json_get["personalization"]["children_names"] == "Luciano, Matteo"

        # Test POST /api/personalization
        res_post = c.post('/api/personalization', json={
            "children_names": "Luciano",
            "pets_names": "Luna",
            "housing_type": "MUTUO",
            "mortgage_bank": "BCC",
            "onboarding_completed": 1
        })
        assert res_post.status_code == 200
        json_post = res_post.get_json()
        assert json_post["success"] is True

        # Test Dashboard render
        res_dash = c.get('/dashboard')
        assert res_dash.status_code == 200
        assert b'personalizationModal' in res_dash.data

        # Test Settings Rules render
        res_rules = c.get('/settings/rules')
        assert res_rules.status_code == 200
        assert b'Profilo Intelligente' in res_rules.data

    print("\nALL SMART PERSONALIZATION TESTS PASSED SUCCESSFULLY!")

if __name__ == '__main__':
    run_tests()
