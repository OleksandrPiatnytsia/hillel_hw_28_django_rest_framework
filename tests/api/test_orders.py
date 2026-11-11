"""The orders API: /api/orders/ and /api/orders/<pk>/cancel/.

- a login for everything (JWT or the session);
- a customer sees only own orders, someone else's -> 404;
- staff reads every order, but can't cancel a customer's one (403,
  IsOwnerOrReadOnly);
- an order is created straight with its items (no cart in the API) by
  orders.services.create_order(): the same stock check and reservation
  as the checkout of the site;
- no PUT / PATCH / DELETE.
"""

from decimal import Decimal

import pytest

from orders.models import Order
from payments.models import Payment
from tests.factories import BookFactory, OrderFactory, PaymentFactory

pytestmark = pytest.mark.django_db


def order_data(*items, **changes):
    """The body of POST /api/orders/; items = (book, quantity) pairs."""
    data = {
        "full_name": "Ann Shevchenko",
        "phone": "+380 (67) 123-45-67",
        "address": "Kyiv, Khreshchatyk 1",
        "items": [{"book_id": book.pk, "quantity": quantity} for book, quantity in items],
    }
    return {**data, **changes}


# ---------------------------------------------------------------------------
# Reading
# ---------------------------------------------------------------------------


def test_anonymous_gets_401_for_orders(api_client):
    assert api_client.get("/api/orders/").status_code == 401
    assert api_client.post("/api/orders/", {}, format="json").status_code == 401


def test_customer_sees_only_own_orders_with_items(as_user, customer, other_customer):
    book = BookFactory(title="Kobzar", price=Decimal("250.50"))
    own = OrderFactory(user=customer, items=[(book, 2)])
    OrderFactory(user=other_customer, items=[(BookFactory(), 1)])

    response = as_user(customer).get("/api/orders/")

    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 1
    order = data["results"][0]
    assert order["id"] == own.pk
    assert order["user"] == "ann"
    assert order["status"] == "new"
    assert order["total"] == "501.00"
    assert order["paid_amount"] == "0.00"
    assert order["amount_due"] == "501.00"
    assert order["can_be_cancelled"] is True
    assert order["site_url"] == f"http://testserver/orders/{own.pk}/"
    assert order["items"] == [
        {
            "book": {"id": book.pk, "title": "Kobzar"},
            "title": "Kobzar",
            "price": "250.50",
            "quantity": 2,
            "cost": "501.00",
        }
    ]


def test_someone_elses_order_is_404_for_a_customer(as_user, customer, other_customer):
    foreign = OrderFactory(user=other_customer)

    response = as_user(customer).get(f"/api/orders/{foreign.pk}/")

    # 404, not 403: a customer can't learn that order #pk exists
    assert response.status_code == 404


def test_staff_reads_every_order(as_user, manager, customer, other_customer):
    OrderFactory(user=customer)
    foreign = OrderFactory(user=other_customer)
    client = as_user(manager)

    assert client.get("/api/orders/").json()["count"] == 2
    assert client.get(f"/api/orders/{foreign.pk}/").status_code == 200


def test_paid_amount_counts_only_succeeded_payments(as_user, customer):
    order = OrderFactory(user=customer, items=[(BookFactory(price=Decimal("300")), 1)])
    PaymentFactory(order=order, amount=Decimal("100.00"), status=Payment.Status.SUCCEEDED)
    PaymentFactory(order=order, amount=Decimal("200.00"), status=Payment.Status.FAILED)

    data = as_user(customer).get(f"/api/orders/{order.pk}/").json()

    assert data["paid_amount"] == "100.00"
    assert data["amount_due"] == "200.00"


def test_orders_filter_by_status(as_user, customer):
    OrderFactory(user=customer)
    cancelled = OrderFactory(user=customer, status=Order.Status.CANCELLED)

    data = as_user(customer).get("/api/orders/?status=cancelled").json()

    assert [order["id"] for order in data["results"]] == [cancelled.pk]


def test_order_list_takes_the_same_number_of_queries_for_any_page_size(
    as_user, customer, django_assert_num_queries
):
    for _ in range(10):
        OrderFactory(user=customer, items=[(BookFactory(), 1), (BookFactory(), 2)])
    client = as_user(customer)

    # COUNT + the orders with the users and the paid sums (one JOIN query)
    # + the lines + their books: 4, not a few queries per order
    with django_assert_num_queries(4):
        response = client.get("/api/orders/")

    assert len(response.json()["results"]) == 10


# ---------------------------------------------------------------------------
# Creating
# ---------------------------------------------------------------------------


def test_customer_creates_an_order_with_a_jwt_token(
    api_client, customer, get_tokens, mailoutbox, django_capture_on_commit_callbacks
):
    kobzar = BookFactory(title="Kobzar", price=Decimal("250.50"), stock=5)
    other = BookFactory(price=Decimal("100.00"), stock=1)
    access = get_tokens(customer)["access"]
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")

    # execute=True: run the on_commit callbacks (the email after COMMIT)
    with django_capture_on_commit_callbacks(execute=True):
        response = api_client.post(
            "/api/orders/",
            # The client also sends a price and a total: they are ignored
            {**order_data((kobzar, 2), (other, 1)), "total": "1.00"},
            format="json",
        )

    assert response.status_code == 201
    order = Order.objects.get()
    assert order.user == customer
    # The prices of the catalog: 250.50 * 2 + 100.00
    assert order.total == Decimal("601.00")
    # The phone in the format of the site
    assert order.phone == "+380671234567"
    assert response.json()["id"] == order.pk
    assert len(response.json()["items"]) == 2
    # The copies are reserved
    kobzar.refresh_from_db()
    other.refresh_from_db()
    assert (kobzar.stock, other.stock) == (3, 0)
    # The "order created" email, like after the checkout of the site
    assert len(mailoutbox) == 1
    assert mailoutbox[0].to == ["ann@example.com"]


def test_not_enough_stock_is_400_and_nothing_is_saved(as_user, customer):
    book = BookFactory(title="Kobzar", stock=1)

    response = as_user(customer).post("/api/orders/", order_data((book, 3)), format="json")

    assert response.status_code == 400
    assert "Kobzar" in response.json()["items"][0]
    assert not Order.objects.exists()
    book.refresh_from_db()
    assert book.stock == 1


@pytest.mark.parametrize(
    "change, field",
    [
        ({"items": []}, "items"),
        ({"items": [{"book_id": 999999, "quantity": 1}]}, "items"),
        ({"phone": "call me"}, "phone"),
        ({"full_name": ""}, "full_name"),
    ],
)
def test_invalid_order_is_400(as_user, customer, change, field):
    data = order_data((BookFactory(), 1))

    response = as_user(customer).post("/api/orders/", {**data, **change}, format="json")

    assert response.status_code == 400
    assert field in response.json()
    assert not Order.objects.exists()


@pytest.mark.parametrize("quantities", [(0,), (1, 2)], ids=["quantity 0", "same book twice"])
def test_wrong_lines_are_400(as_user, customer, quantities):
    book = BookFactory()

    response = as_user(customer).post(
        "/api/orders/",
        order_data(*[(book, quantity) for quantity in quantities]),
        format="json",
    )

    assert response.status_code == 400
    assert "items" in response.json()
    assert not Order.objects.exists()


# ---------------------------------------------------------------------------
# Cancelling, and what an order doesn't allow
# ---------------------------------------------------------------------------


def create_order_via_api(client, book, quantity=2):
    response = client.post("/api/orders/", order_data((book, quantity)), format="json")
    assert response.status_code == 201, response.content
    return response.json()["id"]


def test_customer_cancels_a_new_order_and_the_books_return(as_user, customer):
    book = BookFactory(stock=5)
    client = as_user(customer)
    order_id = create_order_via_api(client, book, quantity=2)

    response = client.post(f"/api/orders/{order_id}/cancel/")

    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"
    assert response.json()["can_be_cancelled"] is False
    book.refresh_from_db()
    assert book.stock == 5


def test_cancel_twice_or_a_paid_order_is_409(as_user, customer):
    client = as_user(customer)
    order_id = create_order_via_api(client, BookFactory(stock=5))
    paid = OrderFactory(user=customer, payment_status=Order.PaymentStatus.PAID)

    client.post(f"/api/orders/{order_id}/cancel/")
    again = client.post(f"/api/orders/{order_id}/cancel/")
    paid_cancel = client.post(f"/api/orders/{paid.pk}/cancel/")

    assert again.status_code == 409
    assert paid_cancel.status_code == 409
    paid.refresh_from_db()
    assert paid.status == Order.Status.NEW


def test_nobody_cancels_someone_elses_order(as_user, customer, other_customer, manager):
    order = OrderFactory(user=customer)

    by_other_customer = as_user(other_customer).post(f"/api/orders/{order.pk}/cancel/")
    by_manager = as_user(manager).post(f"/api/orders/{order.pk}/cancel/")

    # The other customer doesn't see it at all; the manager sees it, but
    # IsOwnerOrReadOnly allows the changes to the owner only
    assert by_other_customer.status_code == 404
    assert by_manager.status_code == 403
    order.refresh_from_db()
    assert order.status == Order.Status.NEW


@pytest.mark.parametrize("method", ["put", "patch", "delete"])
def test_an_order_cannot_be_changed_or_deleted(as_user, customer, method):
    order = OrderFactory(user=customer)

    response = getattr(as_user(customer), method)(
        f"/api/orders/{order.pk}/", {"total": "1.00"}, format="json"
    )

    assert response.status_code == 405
    assert Order.objects.filter(pk=order.pk, total=order.total).exists()
