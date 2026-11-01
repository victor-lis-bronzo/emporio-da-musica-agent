from emporio_da_musica_agent.tools import (
    get_order,
    get_policy,
    get_product_details,
    list_active_promotions,
    search_products,
)


def ids(result):
    return [p["id"] for p in result["produtos"]]


def first_product(name):
    return get_product_details(name)["produtos"][0]


# ---- catalog: only sellable products are suggested ----

def test_search_excludes_out_of_stock():
    # Giannini GF-3D (id 96) has stock 0
    assert 96 not in ids(search_products(category="Violões", max_price=1000))


def test_search_excludes_discontinued_and_coming_soon():
    result = search_products()  # no filters
    assert not {113, 136, 130} & set(ids(result))


def test_search_respects_filters():
    result = search_products(category="Violões", max_price=1000)
    assert result["produtos"]
    for p in result["produtos"]:
        assert p["categoria"] == "Violões"
        assert p.get("preco_final", p.get("preco")) <= 1000


# ---- details: the customer must hear "sold out" ----

def test_details_of_sold_out_product_shows_zero_stock():
    product = first_product("GF-3D")
    assert product["estoque"] == 0


def test_details_of_discontinued_product_shows_status():
    assert first_product("Shelby SN-7C")["status"] == "discontinued"


# ---- prices: promotion vs PIX ----

def test_active_promotion_shows_original_percent_and_final_without_pix():
    # Crafter HT-100 (id 90): 18% off 2399
    product = first_product("Crafter HT-100")
    assert product["preco_original"] == 2399
    assert product["desconto_percent"] == 18
    assert product["preco_final"] == 1967.18
    assert "preco_pix" not in product  # PIX does not stack with promotions


def test_pix_applies_when_no_promotion():
    # Takamine GD20 (id 95): no active promotion
    product = first_product("Takamine GD20")
    assert product["preco"] == 2199
    assert product["preco_pix"] == 2089.05


def test_inactive_promotions_are_ignored():
    # GF-3D has several promotions, all inactive
    assert "preco_original" not in first_product("GF-3D")
    assert len(list_active_promotions()["promocoes"]) == 4


# ---- orders: identity check (LGPD) ----

def test_order_with_correct_email():
    result = get_order(8, "anacarol.ferreira@coldmail.com")
    assert result["status"] == "shipped"
    assert result["cliente_primeiro_nome"] == "Ana"


def test_order_with_phone_in_other_format():
    assert get_order(8, "67996547821")["status"] == "shipped"


def test_order_with_wrong_contact_leaks_nothing():
    result = get_order(8, "outra.pessoa@jmail.com")
    assert list(result) == ["erro"]


def test_unknown_order_gives_same_error_as_wrong_contact():
    assert get_order(9999, "x@y.com") == get_order(8, "x@y.com")


# ---- policies ----

def test_policy_section_exists():
    assert "7 (sete) dias" in get_policy("politica_de_trocas_e_devolucoes")["texto"]


def test_unknown_policy_section_returns_error():
    assert "erro" in get_policy("inexistente")
