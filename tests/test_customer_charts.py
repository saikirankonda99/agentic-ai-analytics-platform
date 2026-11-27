import pandas as pd

from ui.views.customer import customer_chart


def test_product_codes_remain_exact_categorical_labels():
    figure = customer_chart(pd.DataFrame({"product": ["0007", "0010"], "revenue": [60.0, 10.0]}), "CAD")
    assert figure.layout.xaxis.type == "category"
    assert list(figure.data[0].x) == ["0007", "0010"]
    assert list(figure.data[0].y) == [60.0, 10.0]


def test_monthly_chart_keeps_dates_and_does_not_use_product_categories():
    figure = customer_chart(pd.DataFrame({"month": ["2026-01", "2026-03"], "revenue": [40.0, 30.0]}), "CAD")
    assert figure.data[0].type == "scatter"
    assert figure.layout.xaxis.type != "category"
    assert list(figure.data[0].x) == ["2026-01", "2026-03"]
