# MarketBridge Multi-Vendor Marketplace

MarketBridge is a Django marketplace where buyers browse products and sellers manage their own inventory.

## Current Features

- Buyer registration and login
- Seller registration with shop details
- Role-aware redirects for buyers and sellers
- Public product catalog with search, category, and price filters
- Product detail pages
- Seller dashboard with inventory metrics
- Seller product creation, editing, deletion, and reactivation
- SQLite database for local development
- Bootstrap-based server-rendered templates
- Buyer cart and checkout review
- Buyer order history and seller incoming order lines

## Project Structure

```text
multi_vendor/
├── accounts/                 Custom users, registration, login, and roles
├── products/                 Categories, products, catalog, and seller inventory
├── orders/                   Cart, checkout review, and order history
├── templates/                Shared buyer and seller templates
├── multi_vendor/             Django settings and URL configuration
├── manage.py                 Django management entry point
└── db.sqlite3                Local development database after migration
```

## Requirements

- Python 3.13 or compatible Python version
- Django 6.1.1
- Pillow 12.3.0 for image fields

## Setup on Windows

From the project root:

```powershell
py -3.13 -m pip install Django==6.1.1 Pillow==12.3.0
py -3.13 manage.py migrate
py -3.13 manage.py check
```

Start the development server:

```powershell
py -3.13 manage.py runserver 127.0.0.1:8000
```

Open <http://127.0.0.1:8000/> in a browser.

## Main Routes

| Route | Purpose |
| --- | --- |
| `/` | Product storefront |
| `/products/` | Product catalog |
| `/products/<id>/` | Product details |
| `/accounts/register/buyer/` | Buyer registration |
| `/accounts/register/seller/` | Seller registration |
| `/accounts/login/` | Login |
| `/accounts/logout/` | POST logout |
| `/seller/dashboard/` | Seller dashboard |
| `/seller/products/` | Seller inventory |
| `/seller/products/add/` | Add a product |
| `/cart/` | Buyer cart |
| `/checkout/` | Buyer checkout review |
| `/orders/` | Buyer order history |
| `/seller/orders/` | Seller incoming orders |
| `/admin/` | Django admin |

## User Roles

The custom user model in `accounts/models.py` supports three roles:

- **Buyer:** browses the marketplace
- **Seller:** manages a shop and its products
- **Admin:** reserved for marketplace administration and Django staff access

Create an administrator with:

```powershell
py -3.13 manage.py createsuperuser
```

## Important Configuration

The project uses the custom user model configured in `multi_vendor/settings.py`:

```python
AUTH_USER_MODEL = "accounts.User"
```

Do not remove this setting after migrations have been created. Use migrations whenever models change:

```powershell
py -3.13 manage.py makemigrations
py -3.13 manage.py migrate
```

## Feature Availability

Checkout review shows the cart total and checks stock. Online payments and shipment tracking require their respective apps. Marketplace administrators use Django admin.

## Development Checks

Run the system checks before committing changes:

```powershell
py -3.13 manage.py check
py -3.13 manage.py test
```

The local development server is for development only and should not be used as a production server.
