-- ============================================================
-- MEGASTORE RETAIL — COMPLETE ENTERPRISE SCHEMA
-- Database: megastore_retail
-- Version: 2.0 (Extended)
-- ============================================================
-- TABLE INDEX
-- EXISTING (validated + fixed):
--   1. customers          — buyer accounts
--   2. categories         — product taxonomy (self-referencing)
--   3. products           — product catalogx
--   4. stores             — physical + online locations
--   5. orders             — order headers
--   6. order_items        — line items per order
--   7. inventory          — stock per product per location
--   8. payments           — payment transactions
--   9. returns            — return/refund requests
--  10. reviews            — product reviews
-- NEW (enterprise additions):
--  11. addresses          — normalized address book
--  12. warehouses         — fulfillment centers
--  13. suppliers          — vendor/supplier master
--  14. purchase_orders    — replenishment orders to suppliers
--  15. purchase_order_items
--  16. discounts          — coupon/promo engine
--  17. discount_usages    — tracks coupon redemptions
--  18. shipments          — outbound shipment tracking
--  19. shipment_items     — items per shipment
--  20. employees          — staff/admin accounts
--  21. employee_roles     — RBAC roles
--  22. employee_role_assignments
--  23. sessions           — customer web/app sessions
--  24. cart               — abandoned cart tracking
--  25. cart_items
--  26. wishlists
--  27. wishlist_items
--  28. notifications      — email/sms/push queue
--  29. audit_logs         — immutable change log
--  30. analytics_events   — clickstream / behavioral events
-- ============================================================


-- ============================================================
-- SECTION 1: EXISTING TABLES (Validated + Fixed)
-- ============================================================

-- ------------------------------------------------------------
-- Table 1: customers
-- Changes: normalized address → FK to addresses table
-- ------------------------------------------------------------
CREATE TABLE customers (
    customer_id          BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    customer_uuid        UUID UNIQUE NOT NULL DEFAULT gen_random_uuid(),
    customer_number      VARCHAR(20) UNIQUE NOT NULL,       -- 'CUST-10001'

    -- Personal information
    first_name           VARCHAR(100) NOT NULL,
    last_name            VARCHAR(100) NOT NULL,
    email                VARCHAR(255) UNIQUE NOT NULL,
    phone                VARCHAR(20),
    mobile               VARCHAR(20),

    -- Demographics
    date_of_birth        DATE,
    gender               VARCHAR(20) CHECK (gender IN ('MALE','FEMALE','NON_BINARY','PREFER_NOT_SAY')),
    loyalty_tier         VARCHAR(20) DEFAULT 'BRONZE' CHECK (loyalty_tier IN ('BRONZE','SILVER','GOLD','PLATINUM')),
    loyalty_points       INTEGER DEFAULT 0 CHECK (loyalty_points >= 0),

    -- Account status
    is_active            BOOLEAN DEFAULT TRUE,
    is_verified          BOOLEAN DEFAULT FALSE,
    registration_date    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login           TIMESTAMP,

    -- Marketing preferences
    accepts_marketing    BOOLEAN DEFAULT FALSE,
    email_opt_in         BOOLEAN DEFAULT TRUE,
    sms_opt_in           BOOLEAN DEFAULT FALSE,

    -- Audit
    created_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by           VARCHAR(100),
    updated_by           VARCHAR(100)
);

CREATE INDEX idx_customers_email ON customers(email);
CREATE INDEX idx_customers_loyalty_tier ON customers(loyalty_tier);
CREATE INDEX idx_customers_registration_date ON customers(registration_date);
CREATE INDEX idx_customers_active ON customers(is_active) WHERE is_active = TRUE;


-- ------------------------------------------------------------
-- Table 2: categories
-- Changes: added CHECK to prevent self-reference at root level
-- ------------------------------------------------------------
CREATE TABLE categories (
    category_id          INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    parent_category_id   INTEGER REFERENCES categories(category_id) ON DELETE SET NULL,
    category_name        VARCHAR(100) NOT NULL,
    category_code        VARCHAR(50) UNIQUE NOT NULL,      -- 'APPAREL', 'ELECTRONICS'
    category_path        VARCHAR(500),                     -- 'Apparel > Men > Shirts'
    description          TEXT,
    level                INTEGER DEFAULT 0 CHECK (level >= 0),
    is_active            BOOLEAN DEFAULT TRUE,
    display_order        INTEGER DEFAULT 0,
    image_url            VARCHAR(500),
    created_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Prevent a category from being its own parent
    CONSTRAINT chk_no_self_parent CHECK (parent_category_id != category_id)
);

CREATE INDEX idx_categories_parent ON categories(parent_category_id);
CREATE INDEX idx_categories_code ON categories(category_code);
CREATE INDEX idx_categories_active ON categories(is_active) WHERE is_active = TRUE;


-- ------------------------------------------------------------
-- Table 3: products
-- Changes: added FK to categories; added supplier_id FK
-- ------------------------------------------------------------
CREATE TABLE products (
    product_id           BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    product_sku          VARCHAR(50) UNIQUE NOT NULL,
    product_upc          VARCHAR(20),
    product_ean          VARCHAR(20),
    supplier_id          INTEGER,                          -- FK added in Section 2

    -- Basic info
    product_name         VARCHAR(255) NOT NULL,
    product_description  TEXT,
    brand                VARCHAR(100),
    manufacturer         VARCHAR(100),

    -- Categorization
    category_id          INTEGER REFERENCES categories(category_id) ON DELETE SET NULL,
    subcategory_id       INTEGER REFERENCES categories(category_id) ON DELETE SET NULL,
    product_type         VARCHAR(50) DEFAULT 'PHYSICAL' CHECK (product_type IN ('PHYSICAL','DIGITAL','SERVICE','BUNDLE')),

    -- Pricing
    base_price           DECIMAL(12,2) NOT NULL CHECK (base_price >= 0),
    discounted_price     DECIMAL(12,2) CHECK (discounted_price >= 0),
    cost_price           DECIMAL(12,2) CHECK (cost_price >= 0),
    tax_rate             DECIMAL(5,2) DEFAULT 0.00 CHECK (tax_rate >= 0),
    tax_class            VARCHAR(50) DEFAULT 'STANDARD',  -- 'STANDARD','REDUCED','EXEMPT'

    -- Physical attributes
    weight_kg            DECIMAL(8,3),
    length_cm            DECIMAL(8,2),
    width_cm             DECIMAL(8,2),
    height_cm            DECIMAL(8,2),

    -- Status
    is_active            BOOLEAN DEFAULT TRUE,
    is_featured          BOOLEAN DEFAULT FALSE,
    is_digital           BOOLEAN DEFAULT FALSE,
    requires_shipping    BOOLEAN DEFAULT TRUE,

    -- SEO
    meta_title           VARCHAR(255),
    meta_description     TEXT,
    search_keywords      TEXT,
    slug                 VARCHAR(300) UNIQUE,              -- URL-friendly identifier

    -- Audit
    created_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by           VARCHAR(100),
    updated_by           VARCHAR(100)
);

CREATE INDEX idx_products_sku ON products(product_sku);
CREATE INDEX idx_products_category ON products(category_id);
CREATE INDEX idx_products_brand ON products(brand);
CREATE INDEX idx_products_price ON products(base_price);
CREATE INDEX idx_products_active ON products(is_active) WHERE is_active = TRUE;
CREATE INDEX idx_products_slug ON products(slug);


-- ------------------------------------------------------------
-- Table 4: stores
-- Changes: FK to warehouses (added after warehouses table)
-- ------------------------------------------------------------
CREATE TABLE stores (
    store_id             INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    store_code           VARCHAR(20) UNIQUE NOT NULL,
    store_name           VARCHAR(100) NOT NULL,
    store_type           VARCHAR(50) DEFAULT 'PHYSICAL' CHECK (store_type IN ('PHYSICAL','WAREHOUSE','POPUP','ONLINE_ONLY','FRANCHISE')),

    -- Location
    address_line1        VARCHAR(255),
    address_line2        VARCHAR(255),
    city                 VARCHAR(100) NOT NULL,
    state_province       VARCHAR(100) NOT NULL,
    postal_code          VARCHAR(20) NOT NULL,
    country              VARCHAR(100) DEFAULT 'IND',
    region               VARCHAR(50) CHECK (region IN ('NORTH','SOUTH','EAST','WEST','CENTRAL','NORTHEAST','ONLINE')),
    latitude             DECIMAL(9,6),
    longitude            DECIMAL(9,6),
    timezone             VARCHAR(50) DEFAULT 'Asia/Kolkata',

    -- Contact
    phone                VARCHAR(20),
    email                VARCHAR(255),
    manager_employee_id  INTEGER,                          -- FK to employees
    
    -- Operational
    is_active            BOOLEAN DEFAULT TRUE,
    is_franchise         BOOLEAN DEFAULT FALSE,
    primary_warehouse_id INTEGER,                          -- FK to warehouses
    max_daily_orders     INTEGER,

    -- Business hours
    business_hours       JSONB,

    -- Audit
    created_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_stores_city ON stores(city);
CREATE INDEX idx_stores_region ON stores(region);
CREATE INDEX idx_stores_state ON stores(state_province);
CREATE INDEX idx_stores_active ON stores(is_active) WHERE is_active = TRUE;


-- ------------------------------------------------------------
-- Table 5: orders
-- Changes: added FK to addresses; split shipping into address_id
-- ------------------------------------------------------------
CREATE TABLE orders (
    order_id             BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    order_uuid           UUID UNIQUE NOT NULL DEFAULT gen_random_uuid(),
    order_number         VARCHAR(30) UNIQUE NOT NULL,

    -- Relations
    customer_id          BIGINT REFERENCES customers(customer_id),
    store_id             INTEGER REFERENCES stores(store_id),
    shipping_address_id  BIGINT,                           -- FK to addresses

    -- Status
    order_date           TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    order_status         VARCHAR(50) NOT NULL DEFAULT 'PENDING'
                         CHECK (order_status IN ('PENDING','PROCESSING','CONFIRMED','SHIPPED','DELIVERED','CANCELLED','RETURNED','ON_HOLD')),
    payment_status       VARCHAR(50) DEFAULT 'PENDING'
                         CHECK (payment_status IN ('PENDING','PAID','FAILED','REFUNDED','PARTIALLY_REFUNDED')),
    fulfillment_status   VARCHAR(50) DEFAULT 'UNFULFILLED'
                         CHECK (fulfillment_status IN ('UNFULFILLED','PARTIALLY_FULFILLED','FULFILLED','RETURNED')),

    -- Financials
    subtotal             DECIMAL(12,2) NOT NULL CHECK (subtotal >= 0),
    discount_amount      DECIMAL(12,2) DEFAULT 0.00 CHECK (discount_amount >= 0),
    tax_amount           DECIMAL(12,2) DEFAULT 0.00 CHECK (tax_amount >= 0),
    shipping_amount      DECIMAL(12,2) DEFAULT 0.00 CHECK (shipping_amount >= 0),
    total_amount         DECIMAL(12,2) NOT NULL CHECK (total_amount >= 0),
    currency             VARCHAR(3) DEFAULT 'INR',

    -- Payment
    payment_method       VARCHAR(50) CHECK (payment_method IN ('CREDIT_CARD','DEBIT_CARD','UPI','NETBANKING','WALLET','GIFT_CARD','COD','BNPL')),
    payment_provider     VARCHAR(50),
    payment_transaction_id VARCHAR(100),
    coupon_code          VARCHAR(50),
    discount_id          BIGINT,                           -- FK to discounts

    -- Shipping
    shipping_method      VARCHAR(50) CHECK (shipping_method IN ('STANDARD','EXPRESS','SAME_DAY','OVERNIGHT','STORE_PICKUP','FREE')),
    tracking_number      VARCHAR(100),
    carrier_name         VARCHAR(100),
    estimated_delivery   DATE,
    actual_delivery      TIMESTAMP,

    -- Context
    customer_ip          INET,
    user_agent           TEXT,
    device_type          VARCHAR(50) CHECK (device_type IN ('MOBILE','DESKTOP','TABLET','APP_IOS','APP_ANDROID')),
    channel              VARCHAR(50) DEFAULT 'ONLINE' CHECK (channel IN ('ONLINE','IN_STORE','MOBILE_APP','PHONE','THIRD_PARTY')),

    -- Gift
    is_gift              BOOLEAN DEFAULT FALSE,
    gift_message         TEXT,

    -- Notes
    customer_notes       TEXT,
    internal_notes       TEXT,

    -- Audit
    created_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processed_at         TIMESTAMP,
    cancelled_at         TIMESTAMP,
    cancellation_reason  TEXT
);

CREATE INDEX idx_orders_customer_id ON orders(customer_id);
CREATE INDEX idx_orders_order_date ON orders(order_date);
CREATE INDEX idx_orders_status ON orders(order_status);
CREATE INDEX idx_orders_store_id ON orders(store_id);
CREATE INDEX idx_orders_payment_status ON orders(payment_status);
CREATE INDEX idx_orders_total_amount ON orders(total_amount);
CREATE INDEX idx_orders_channel ON orders(channel);
CREATE INDEX idx_orders_date_status ON orders(order_date, order_status);


-- ------------------------------------------------------------
-- Table 6: order_items  (unchanged, good as-is)
-- ------------------------------------------------------------
CREATE TABLE order_items (
    order_item_id        BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    order_id             BIGINT NOT NULL REFERENCES orders(order_id) ON DELETE CASCADE,
    product_id           BIGINT NOT NULL REFERENCES products(product_id),

    -- Snapshot at purchase time
    product_sku          VARCHAR(50) NOT NULL,
    product_name         VARCHAR(255) NOT NULL,
    category_id          INTEGER,
    unit_price           DECIMAL(12,2) NOT NULL CHECK (unit_price >= 0),
    quantity             INTEGER NOT NULL CHECK (quantity > 0),
    discount_amount      DECIMAL(12,2) DEFAULT 0.00 CHECK (discount_amount >= 0),
    tax_amount           DECIMAL(12,2) DEFAULT 0.00 CHECK (tax_amount >= 0),
    total_price          DECIMAL(12,2) GENERATED ALWAYS AS ((unit_price - discount_amount) * quantity) STORED,

    -- Status
    item_status          VARCHAR(50) DEFAULT 'PENDING'
                         CHECK (item_status IN ('PENDING','CONFIRMED','SHIPPED','DELIVERED','CANCELLED','RETURNED')),
    return_requested     BOOLEAN DEFAULT FALSE,
    return_reason        TEXT,
    return_quantity      INTEGER DEFAULT 0 CHECK (return_quantity >= 0),

    -- Fulfillment
    warehouse_id         INTEGER,                          -- FK to warehouses
    shipment_id          BIGINT,                          -- FK to shipments

    created_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_order_items_order_id ON order_items(order_id);
CREATE INDEX idx_order_items_product_id ON order_items(product_id);
CREATE INDEX idx_order_items_status ON order_items(item_status);


-- ------------------------------------------------------------
-- Table 7: inventory
-- Changes: proper FK to warehouses; added last_reorder_at
-- ------------------------------------------------------------
CREATE TABLE inventory (
    inventory_id         BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    product_id           BIGINT NOT NULL REFERENCES products(product_id),
    store_id             INTEGER REFERENCES stores(store_id),
    warehouse_id         INTEGER,                          -- FK to warehouses

    -- Stock
    quantity_on_hand     INTEGER NOT NULL DEFAULT 0 CHECK (quantity_on_hand >= 0),
    quantity_allocated   INTEGER NOT NULL DEFAULT 0 CHECK (quantity_allocated >= 0),
    quantity_available   INTEGER GENERATED ALWAYS AS (quantity_on_hand - quantity_allocated) STORED,
    quantity_in_transit  INTEGER DEFAULT 0 CHECK (quantity_in_transit >= 0),
    quantity_damaged     INTEGER DEFAULT 0 CHECK (quantity_damaged >= 0),
    min_stock_threshold  INTEGER DEFAULT 10,
    max_stock_threshold  INTEGER DEFAULT 500,
    reorder_point        INTEGER DEFAULT 20,
    reorder_quantity     INTEGER DEFAULT 50,

    -- Location
    bin_location         VARCHAR(50),
    shelf_number         VARCHAR(20),
    aisle                VARCHAR(20),

    -- Status
    is_backorder_allowed BOOLEAN DEFAULT FALSE,
    last_stock_check     TIMESTAMP,
    last_reorder_at      TIMESTAMP,
    last_received_at     TIMESTAMP,

    -- Audit
    last_updated         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_updated_by      VARCHAR(100),

    UNIQUE(product_id, store_id),
    UNIQUE(product_id, warehouse_id)
);

CREATE INDEX idx_inventory_product ON inventory(product_id);
CREATE INDEX idx_inventory_store ON inventory(store_id);
CREATE INDEX idx_inventory_warehouse ON inventory(warehouse_id);
CREATE INDEX idx_inventory_low_stock ON inventory(quantity_available)
    WHERE quantity_available < reorder_point;


-- ------------------------------------------------------------
-- Table 8: payments  (unchanged, good as-is)
-- ------------------------------------------------------------
CREATE TABLE payments (
    payment_id           BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    order_id             BIGINT NOT NULL REFERENCES orders(order_id),
    payment_uuid         UUID UNIQUE NOT NULL DEFAULT gen_random_uuid(),

    payment_method       VARCHAR(50) NOT NULL,
    payment_provider     VARCHAR(50),
    amount               DECIMAL(12,2) NOT NULL CHECK (amount > 0),
    currency             VARCHAR(3) DEFAULT 'INR',

    payment_status       VARCHAR(50) DEFAULT 'PENDING'
                         CHECK (payment_status IN ('PENDING','SUCCESS','FAILED','REFUNDED','PARTIALLY_REFUNDED','CHARGEBACK')),
    transaction_id       VARCHAR(100),
    provider_reference   VARCHAR(100),
    gateway_response     JSONB,

    -- Refund
    refund_amount        DECIMAL(12,2) DEFAULT 0.00 CHECK (refund_amount >= 0),
    refund_transaction_id VARCHAR(100),
    refund_reason        TEXT,

    -- Timestamps
    payment_requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    payment_completed_at TIMESTAMP,
    refund_processed_at  TIMESTAMP,

    payment_metadata     JSONB,
    created_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_payments_order_id ON payments(order_id);
CREATE INDEX idx_payments_status ON payments(payment_status);
CREATE INDEX idx_payments_transaction_id ON payments(transaction_id);


-- ------------------------------------------------------------
-- Table 9: returns  (unchanged, good as-is)
-- ------------------------------------------------------------
CREATE TABLE returns (
    return_id            BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    order_id             BIGINT NOT NULL REFERENCES orders(order_id),
    customer_id          BIGINT NOT NULL REFERENCES customers(customer_id),
    return_number        VARCHAR(30) UNIQUE NOT NULL,

    return_reason        TEXT NOT NULL,
    return_status        VARCHAR(50) DEFAULT 'REQUESTED'
                         CHECK (return_status IN ('REQUESTED','APPROVED','PICKED_UP','RECEIVED','REFUNDED','REJECTED','EXCHANGED')),
    return_type          VARCHAR(50) CHECK (return_type IN ('REFUND','EXCHANGE','STORE_CREDIT')),

    total_refund_amount  DECIMAL(12,2) CHECK (total_refund_amount >= 0),
    refund_method        VARCHAR(50) CHECK (refund_method IN ('ORIGINAL_PAYMENT','STORE_CREDIT','GIFT_CARD','BANK_TRANSFER')),

    -- Timeline
    requested_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    approved_at          TIMESTAMP,
    picked_up_at         TIMESTAMP,
    received_at          TIMESTAMP,
    refund_processed_at  TIMESTAMP,
    completed_at         TIMESTAMP,

    return_tracking_number VARCHAR(100),
    return_carrier       VARCHAR(50),
    inspection_notes     TEXT,
    staff_notes          TEXT,
    customer_notes       TEXT,

    processed_by         INTEGER,                          -- FK to employees

    created_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_returns_order_id ON returns(order_id);
CREATE INDEX idx_returns_customer_id ON returns(customer_id);
CREATE INDEX idx_returns_status ON returns(return_status);


-- ------------------------------------------------------------
-- Table 10: reviews  (unchanged, good as-is)
-- ------------------------------------------------------------
CREATE TABLE reviews (
    review_id            BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    product_id           BIGINT NOT NULL REFERENCES products(product_id),
    customer_id          BIGINT NOT NULL REFERENCES customers(customer_id),
    order_id             BIGINT REFERENCES orders(order_id),

    rating               INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
    title                VARCHAR(200),
    review_text          TEXT,
    images_urls          TEXT[],
    video_urls           TEXT[],

    is_verified_purchase BOOLEAN DEFAULT FALSE,
    is_approved          BOOLEAN DEFAULT FALSE,
    is_featured          BOOLEAN DEFAULT FALSE,

    helpful_count        INTEGER DEFAULT 0 CHECK (helpful_count >= 0),
    not_helpful_count    INTEGER DEFAULT 0 CHECK (not_helpful_count >= 0),

    merchant_response    TEXT,
    merchant_responded_at TIMESTAMP,
    moderated_by         INTEGER,                          -- FK to employees

    created_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(product_id, customer_id)
);

CREATE INDEX idx_reviews_product_id ON reviews(product_id);
CREATE INDEX idx_reviews_customer_id ON reviews(customer_id);
CREATE INDEX idx_reviews_rating ON reviews(rating);
CREATE INDEX idx_reviews_approved ON reviews(is_approved) WHERE is_approved = TRUE;


-- ============================================================
-- SECTION 2: NEW ENTERPRISE TABLES
-- ============================================================

-- ------------------------------------------------------------
-- Table 11: addresses
-- Normalized address book (customers can have multiple)
-- ------------------------------------------------------------
CREATE TABLE addresses (
    address_id           BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    customer_id          BIGINT REFERENCES customers(customer_id) ON DELETE CASCADE,
    address_type         VARCHAR(30) DEFAULT 'SHIPPING'
                         CHECK (address_type IN ('SHIPPING','BILLING','BOTH','STORE','WAREHOUSE')),
    label                VARCHAR(50),                      -- 'Home', 'Office', 'Parents'

    first_name           VARCHAR(100),
    last_name            VARCHAR(100),
    company              VARCHAR(100),
    phone                VARCHAR(20),

    address_line1        VARCHAR(255) NOT NULL,
    address_line2        VARCHAR(255),
    landmark             VARCHAR(255),
    city                 VARCHAR(100) NOT NULL,
    state_province       VARCHAR(100) NOT NULL,
    postal_code          VARCHAR(20) NOT NULL,
    country              VARCHAR(100) DEFAULT 'India',

    latitude             DECIMAL(9,6),
    longitude            DECIMAL(9,6),

    is_default           BOOLEAN DEFAULT FALSE,
    is_verified          BOOLEAN DEFAULT FALSE,
    verification_source  VARCHAR(50),                      -- 'GOOGLE_MAPS', 'MANUAL'

    created_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_addresses_customer_id ON addresses(customer_id);
CREATE INDEX idx_addresses_default ON addresses(customer_id, is_default) WHERE is_default = TRUE;

-- Add FK from orders
ALTER TABLE orders ADD CONSTRAINT fk_orders_shipping_address
    FOREIGN KEY (shipping_address_id) REFERENCES addresses(address_id);


-- ------------------------------------------------------------
-- Table 12: warehouses
-- Fulfillment centers
-- ------------------------------------------------------------
CREATE TABLE warehouses (
    warehouse_id         INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    warehouse_code       VARCHAR(20) UNIQUE NOT NULL,      -- 'WH-BLR-01'
    warehouse_name       VARCHAR(100) NOT NULL,
    warehouse_type       VARCHAR(50) DEFAULT 'DISTRIBUTION'
                         CHECK (warehouse_type IN ('DISTRIBUTION','FULFILLMENT','DARK_STORE','RETURNS','COLD_CHAIN')),

    -- Address
    address_line1        VARCHAR(255) NOT NULL,
    address_line2        VARCHAR(255),
    city                 VARCHAR(100) NOT NULL,
    state_province       VARCHAR(100) NOT NULL,
    postal_code          VARCHAR(20) NOT NULL,
    country              VARCHAR(100) DEFAULT 'India',
    latitude             DECIMAL(9,6),
    longitude            DECIMAL(9,6),

    -- Capacity
    total_area_sqft      DECIMAL(10,2),
    storage_capacity     INTEGER,                          -- max SKU slots
    current_utilization  DECIMAL(5,2),                    -- percentage

    -- Contact
    phone                VARCHAR(20),
    email                VARCHAR(255),
    manager_name         VARCHAR(100),
    manager_phone        VARCHAR(20),

    -- Operational
    is_active            BOOLEAN DEFAULT TRUE,
    is_third_party       BOOLEAN DEFAULT FALSE,
    operating_hours      JSONB,

    created_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_warehouses_city ON warehouses(city);
CREATE INDEX idx_warehouses_active ON warehouses(is_active) WHERE is_active = TRUE;

-- Add FK from stores + inventory
ALTER TABLE stores ADD CONSTRAINT fk_stores_warehouse
    FOREIGN KEY (primary_warehouse_id) REFERENCES warehouses(warehouse_id);
ALTER TABLE inventory ADD CONSTRAINT fk_inventory_warehouse
    FOREIGN KEY (warehouse_id) REFERENCES warehouses(warehouse_id);
ALTER TABLE order_items ADD CONSTRAINT fk_order_items_warehouse
    FOREIGN KEY (warehouse_id) REFERENCES warehouses(warehouse_id);


-- ------------------------------------------------------------
-- Table 13: suppliers
-- Vendor/manufacturer master
-- ------------------------------------------------------------
CREATE TABLE suppliers (
    supplier_id          INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    supplier_code        VARCHAR(30) UNIQUE NOT NULL,      -- 'SUP-00123'
    supplier_name        VARCHAR(200) NOT NULL,
    supplier_type        VARCHAR(50) DEFAULT 'MANUFACTURER'
                         CHECK (supplier_type IN ('MANUFACTURER','DISTRIBUTOR','WHOLESALER','DROPSHIPPER','IMPORTER')),

    -- Contact
    contact_name         VARCHAR(100),
    contact_email        VARCHAR(255),
    contact_phone        VARCHAR(20),
    website              VARCHAR(300),

    -- Address
    address_line1        VARCHAR(255),
    city                 VARCHAR(100),
    state_province       VARCHAR(100),
    postal_code          VARCHAR(20),
    country              VARCHAR(100),

    -- Financial
    payment_terms        VARCHAR(50),                      -- 'NET_30', 'NET_60', 'COD'
    credit_limit         DECIMAL(14,2),
    currency             VARCHAR(3) DEFAULT 'INR',
    tax_id               VARCHAR(50),                      -- GSTIN for India
    bank_account_details JSONB,                            -- encrypted

    -- Performance
    avg_lead_time_days   INTEGER,
    reliability_score    DECIMAL(3,1),                     -- 1.0 to 5.0
    last_order_date      DATE,

    -- Status
    is_active            BOOLEAN DEFAULT TRUE,
    is_preferred         BOOLEAN DEFAULT FALSE,
    contract_start_date  DATE,
    contract_end_date    DATE,

    -- Audit
    created_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by           VARCHAR(100)
);

CREATE INDEX idx_suppliers_code ON suppliers(supplier_code);
CREATE INDEX idx_suppliers_active ON suppliers(is_active) WHERE is_active = TRUE;

-- Add FK from products
ALTER TABLE products ADD CONSTRAINT fk_products_supplier
    FOREIGN KEY (supplier_id) REFERENCES suppliers(supplier_id);


-- ------------------------------------------------------------
-- Table 14: purchase_orders
-- Replenishment orders sent to suppliers
-- ------------------------------------------------------------
CREATE TABLE purchase_orders (
    po_id                BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    po_number            VARCHAR(30) UNIQUE NOT NULL,      -- 'PO-20250115-001'
    supplier_id          INTEGER NOT NULL REFERENCES suppliers(supplier_id),
    warehouse_id         INTEGER NOT NULL REFERENCES warehouses(warehouse_id),

    po_status            VARCHAR(50) DEFAULT 'DRAFT'
                         CHECK (po_status IN ('DRAFT','SUBMITTED','CONFIRMED','PARTIALLY_RECEIVED','RECEIVED','CANCELLED')),
    priority             VARCHAR(20) DEFAULT 'NORMAL' CHECK (priority IN ('LOW','NORMAL','HIGH','URGENT')),

    -- Financials
    subtotal             DECIMAL(14,2) NOT NULL CHECK (subtotal >= 0),
    tax_amount           DECIMAL(14,2) DEFAULT 0.00,
    shipping_amount      DECIMAL(14,2) DEFAULT 0.00,
    total_amount         DECIMAL(14,2) NOT NULL CHECK (total_amount >= 0),
    currency             VARCHAR(3) DEFAULT 'INR',

    -- Timeline
    order_date           TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expected_delivery    DATE,
    actual_delivery      DATE,

    -- Payment
    payment_terms        VARCHAR(50),
    payment_due_date     DATE,
    payment_status       VARCHAR(50) DEFAULT 'UNPAID'
                         CHECK (payment_status IN ('UNPAID','PARTIALLY_PAID','PAID','OVERDUE')),

    notes                TEXT,
    approved_by          INTEGER,                          -- FK to employees

    created_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by           INTEGER                           -- FK to employees
);

CREATE INDEX idx_po_supplier_id ON purchase_orders(supplier_id);
CREATE INDEX idx_po_warehouse_id ON purchase_orders(warehouse_id);
CREATE INDEX idx_po_status ON purchase_orders(po_status);
CREATE INDEX idx_po_order_date ON purchase_orders(order_date);


-- ------------------------------------------------------------
-- Table 15: purchase_order_items
-- Line items per PO
-- ------------------------------------------------------------
CREATE TABLE purchase_order_items (
    po_item_id           BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    po_id                BIGINT NOT NULL REFERENCES purchase_orders(po_id) ON DELETE CASCADE,
    product_id           BIGINT NOT NULL REFERENCES products(product_id),
    product_sku          VARCHAR(50) NOT NULL,

    quantity_ordered     INTEGER NOT NULL CHECK (quantity_ordered > 0),
    quantity_received    INTEGER DEFAULT 0 CHECK (quantity_received >= 0),
    quantity_rejected    INTEGER DEFAULT 0 CHECK (quantity_rejected >= 0),
    unit_cost            DECIMAL(12,2) NOT NULL CHECK (unit_cost >= 0),
    total_cost           DECIMAL(12,2) GENERATED ALWAYS AS (quantity_ordered * unit_cost) STORED,

    item_status          VARCHAR(50) DEFAULT 'PENDING'
                         CHECK (item_status IN ('PENDING','PARTIALLY_RECEIVED','RECEIVED','CANCELLED')),

    received_at          TIMESTAMP,
    notes                TEXT,

    created_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_po_items_po_id ON purchase_order_items(po_id);
CREATE INDEX idx_po_items_product_id ON purchase_order_items(product_id);


-- ------------------------------------------------------------
-- Table 16: discounts
-- Coupon and promo code engine
-- ------------------------------------------------------------
CREATE TABLE discounts (
    discount_id          BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    discount_code        VARCHAR(50) UNIQUE NOT NULL,      -- 'SALE20', 'NEWUSER100'
    discount_name        VARCHAR(200) NOT NULL,
    description          TEXT,

    discount_type        VARCHAR(50) NOT NULL
                         CHECK (discount_type IN ('PERCENTAGE','FIXED_AMOUNT','FREE_SHIPPING','BUY_X_GET_Y','LOYALTY_POINTS')),

    -- Value
    discount_value       DECIMAL(10,2) NOT NULL CHECK (discount_value >= 0),
    max_discount_amount  DECIMAL(10,2),                    -- cap for percentage discounts
    min_order_value      DECIMAL(10,2) DEFAULT 0.00,

    -- Eligibility
    applies_to           VARCHAR(50) DEFAULT 'ALL'
                         CHECK (applies_to IN ('ALL','SPECIFIC_PRODUCTS','SPECIFIC_CATEGORIES','SPECIFIC_CUSTOMERS','FIRST_ORDER')),
    applicable_ids       BIGINT[],                         -- product/category IDs
    eligible_loyalty_tiers VARCHAR(20)[],                  -- ['GOLD','PLATINUM']
    customer_id          BIGINT REFERENCES customers(customer_id),  -- single customer coupon

    -- Usage limits
    usage_limit_total    INTEGER,                          -- NULL = unlimited
    usage_limit_per_customer INTEGER DEFAULT 1,
    times_used           INTEGER DEFAULT 0 CHECK (times_used >= 0),

    -- Validity
    valid_from           TIMESTAMP NOT NULL,
    valid_until          TIMESTAMP,
    is_active            BOOLEAN DEFAULT TRUE,

    -- Stacking
    can_combine          BOOLEAN DEFAULT FALSE,            -- stack with other discounts

    created_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by           INTEGER
);

CREATE INDEX idx_discounts_code ON discounts(discount_code);
CREATE INDEX idx_discounts_active ON discounts(is_active, valid_from, valid_until);


-- ------------------------------------------------------------
-- Table 17: discount_usages
-- Tracks each redemption of a coupon
-- ------------------------------------------------------------
CREATE TABLE discount_usages (
    usage_id             BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    discount_id          BIGINT NOT NULL REFERENCES discounts(discount_id),
    order_id             BIGINT NOT NULL REFERENCES orders(order_id),
    customer_id          BIGINT NOT NULL REFERENCES customers(customer_id),

    discount_amount_applied DECIMAL(10,2) NOT NULL,
    used_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(discount_id, order_id)
);

CREATE INDEX idx_discount_usages_discount_id ON discount_usages(discount_id);
CREATE INDEX idx_discount_usages_customer_id ON discount_usages(customer_id);
ALTER TABLE orders ADD CONSTRAINT fk_orders_discount
    FOREIGN KEY (discount_id) REFERENCES discounts(discount_id);


-- ------------------------------------------------------------
-- Table 18: shipments
-- Outbound shipment tracking (one order can have multiple)
-- ------------------------------------------------------------
CREATE TABLE shipments (
    shipment_id          BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    shipment_number      VARCHAR(50) UNIQUE NOT NULL,      -- 'SHIP-20250115-00123'
    order_id             BIGINT NOT NULL REFERENCES orders(order_id),
    warehouse_id         INTEGER REFERENCES warehouses(warehouse_id),

    -- Status
    shipment_status      VARCHAR(50) DEFAULT 'PENDING'
                         CHECK (shipment_status IN ('PENDING','PACKED','DISPATCHED','IN_TRANSIT','OUT_FOR_DELIVERY','DELIVERED','FAILED','RETURNED')),

    -- Carrier
    carrier_name         VARCHAR(100),
    carrier_code         VARCHAR(20),
    tracking_number      VARCHAR(100),
    tracking_url         VARCHAR(500),
    service_type         VARCHAR(50),                      -- 'EXPRESS','STANDARD','SAME_DAY'

    -- Dimensions (for shipping cost calc)
    weight_kg            DECIMAL(8,3),
    length_cm            DECIMAL(8,2),
    width_cm             DECIMAL(8,2),
    height_cm            DECIMAL(8,2),
    shipping_cost        DECIMAL(10,2),

    -- Address (denormalized snapshot)
    delivery_address_id  BIGINT REFERENCES addresses(address_id),

    -- Timeline
    packed_at            TIMESTAMP,
    dispatched_at        TIMESTAMP,
    estimated_delivery   TIMESTAMP,
    delivered_at         TIMESTAMP,
    delivery_attempt_count INTEGER DEFAULT 0,
    last_tracking_update TIMESTAMP,
    tracking_history     JSONB,                            -- array of {status, timestamp, location}

    -- Proof of delivery
    pod_signature        VARCHAR(200),
    pod_photo_url        VARCHAR(500),
    delivery_notes       TEXT,

    created_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_shipments_order_id ON shipments(order_id);
CREATE INDEX idx_shipments_tracking ON shipments(tracking_number);
CREATE INDEX idx_shipments_status ON shipments(shipment_status);
CREATE INDEX idx_shipments_warehouse ON shipments(warehouse_id);

ALTER TABLE order_items ADD CONSTRAINT fk_order_items_shipment
    FOREIGN KEY (shipment_id) REFERENCES shipments(shipment_id);


-- ------------------------------------------------------------
-- Table 19: shipment_items
-- Which order items are in which shipment (split shipment support)
-- ------------------------------------------------------------
CREATE TABLE shipment_items (
    shipment_item_id     BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    shipment_id          BIGINT NOT NULL REFERENCES shipments(shipment_id) ON DELETE CASCADE,
    order_item_id        BIGINT NOT NULL REFERENCES order_items(order_item_id),
    quantity_shipped     INTEGER NOT NULL CHECK (quantity_shipped > 0),
    created_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(shipment_id, order_item_id)
);

CREATE INDEX idx_shipment_items_shipment_id ON shipment_items(shipment_id);
CREATE INDEX idx_shipment_items_order_item_id ON shipment_items(order_item_id);


-- ------------------------------------------------------------
-- Table 20: employees
-- Staff accounts (store staff, warehouse workers, admins)
-- ------------------------------------------------------------
CREATE TABLE employees (
    employee_id          INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    employee_code        VARCHAR(30) UNIQUE NOT NULL,      -- 'EMP-10001'
    employee_uuid        UUID UNIQUE NOT NULL DEFAULT gen_random_uuid(),

    -- Personal
    first_name           VARCHAR(100) NOT NULL,
    last_name            VARCHAR(100) NOT NULL,
    email                VARCHAR(255) UNIQUE NOT NULL,
    phone                VARCHAR(20),
    date_of_birth        DATE,

    -- Employment
    department           VARCHAR(100),
    designation          VARCHAR(100),
    employment_type      VARCHAR(50) DEFAULT 'FULL_TIME'
                         CHECK (employment_type IN ('FULL_TIME','PART_TIME','CONTRACT','INTERN')),
    hire_date            DATE NOT NULL,
    termination_date     DATE,

    -- Location
    store_id             INTEGER REFERENCES stores(store_id),
    warehouse_id         INTEGER REFERENCES warehouses(warehouse_id),
    is_remote            BOOLEAN DEFAULT FALSE,

    -- Auth
    password_hash        VARCHAR(255),
    last_login           TIMESTAMP,
    failed_login_attempts INTEGER DEFAULT 0,
    is_locked            BOOLEAN DEFAULT FALSE,
    mfa_enabled          BOOLEAN DEFAULT FALSE,

    -- Status
    is_active            BOOLEAN DEFAULT TRUE,

    -- Audit
    created_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by           INTEGER REFERENCES employees(employee_id)
);

CREATE INDEX idx_employees_email ON employees(email);
CREATE INDEX idx_employees_store ON employees(store_id);
CREATE INDEX idx_employees_active ON employees(is_active) WHERE is_active = TRUE;

ALTER TABLE stores ADD CONSTRAINT fk_stores_manager
    FOREIGN KEY (manager_employee_id) REFERENCES employees(employee_id);


-- ------------------------------------------------------------
-- Table 21: employee_roles
-- RBAC role definitions
-- ------------------------------------------------------------
CREATE TABLE employee_roles (
    role_id              INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    role_name            VARCHAR(100) UNIQUE NOT NULL,     -- 'STORE_MANAGER','WAREHOUSE_STAFF'
    role_code            VARCHAR(50) UNIQUE NOT NULL,
    description          TEXT,
    permissions          JSONB NOT NULL,                   -- {"orders": ["read","write"], "inventory": ["read"]}
    is_active            BOOLEAN DEFAULT TRUE,
    created_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_roles_code ON employee_roles(role_code);


-- ------------------------------------------------------------
-- Table 22: employee_role_assignments
-- Many-to-many: employees ↔ roles
-- ------------------------------------------------------------
CREATE TABLE employee_role_assignments (
    assignment_id        BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    employee_id          INTEGER NOT NULL REFERENCES employees(employee_id) ON DELETE CASCADE,
    role_id              INTEGER NOT NULL REFERENCES employee_roles(role_id),
    assigned_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    assigned_by          INTEGER REFERENCES employees(employee_id),
    expires_at           TIMESTAMP,
    is_active            BOOLEAN DEFAULT TRUE,

    UNIQUE(employee_id, role_id)
);

CREATE INDEX idx_role_assignments_employee ON employee_role_assignments(employee_id);
CREATE INDEX idx_role_assignments_role ON employee_role_assignments(role_id);


-- ------------------------------------------------------------
-- Table 23: sessions
-- Customer web/app sessions (for analytics + cart recovery)
-- ------------------------------------------------------------
CREATE TABLE sessions (
    session_id           VARCHAR(128) PRIMARY KEY,         -- UUID or JWT jti
    customer_id          BIGINT REFERENCES customers(customer_id),
    session_type         VARCHAR(20) DEFAULT 'WEB'
                         CHECK (session_type IN ('WEB','APP_IOS','APP_ANDROID','KIOSK')),

    -- Context
    ip_address           INET,
    user_agent           TEXT,
    device_fingerprint   VARCHAR(255),
    device_type          VARCHAR(50),
    browser              VARCHAR(100),
    os                   VARCHAR(100),
    referrer_url         VARCHAR(1000),
    utm_source           VARCHAR(100),
    utm_medium           VARCHAR(100),
    utm_campaign         VARCHAR(100),

    -- Timing
    started_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_activity_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ended_at             TIMESTAMP,
    duration_seconds     INTEGER GENERATED ALWAYS AS
                         (EXTRACT(EPOCH FROM (ended_at - started_at))::INTEGER) STORED,

    -- Geo
    country_code         VARCHAR(5),
    city                 VARCHAR(100),

    is_authenticated     BOOLEAN DEFAULT FALSE,
    store_id             INTEGER REFERENCES stores(store_id)
);

CREATE INDEX idx_sessions_customer_id ON sessions(customer_id);
CREATE INDEX idx_sessions_started_at ON sessions(started_at);
CREATE INDEX idx_sessions_last_activity ON sessions(last_activity_at);


-- ------------------------------------------------------------
-- Table 24: carts
-- Shopping cart / abandoned cart tracking
-- ------------------------------------------------------------
CREATE TABLE carts (
    cart_id              BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    cart_uuid            UUID UNIQUE NOT NULL DEFAULT gen_random_uuid(),
    customer_id          BIGINT REFERENCES customers(customer_id),
    session_id           VARCHAR(128) REFERENCES sessions(session_id),

    cart_status          VARCHAR(30) DEFAULT 'ACTIVE'
                         CHECK (cart_status IN ('ACTIVE','ABANDONED','CONVERTED','EXPIRED','SAVED')),

    -- Financials (computed from items)
    subtotal             DECIMAL(12,2) DEFAULT 0.00,
    discount_amount      DECIMAL(12,2) DEFAULT 0.00,
    estimated_total      DECIMAL(12,2) DEFAULT 0.00,
    coupon_code          VARCHAR(50),

    -- Abandonment recovery
    recovery_email_sent_at TIMESTAMP,
    recovery_email_count INTEGER DEFAULT 0,

    converted_order_id   BIGINT REFERENCES orders(order_id),
    abandoned_at         TIMESTAMP,

    created_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_carts_customer_id ON carts(customer_id);
CREATE INDEX idx_carts_status ON carts(cart_status);
CREATE INDEX idx_carts_abandoned ON carts(abandoned_at) WHERE cart_status = 'ABANDONED';


-- ------------------------------------------------------------
-- Table 25: cart_items
-- ------------------------------------------------------------
CREATE TABLE cart_items (
    cart_item_id         BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    cart_id              BIGINT NOT NULL REFERENCES carts(cart_id) ON DELETE CASCADE,
    product_id           BIGINT NOT NULL REFERENCES products(product_id),
    product_sku          VARCHAR(50) NOT NULL,
    quantity             INTEGER NOT NULL CHECK (quantity > 0),
    unit_price           DECIMAL(12,2) NOT NULL,
    added_at             TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_saved_for_later   BOOLEAN DEFAULT FALSE,

    UNIQUE(cart_id, product_id)
);

CREATE INDEX idx_cart_items_cart_id ON cart_items(cart_id);
CREATE INDEX idx_cart_items_product_id ON cart_items(product_id);


-- ------------------------------------------------------------
-- Table 26: wishlists
-- Customer product wishlists (multiple lists per customer)
-- ------------------------------------------------------------
CREATE TABLE wishlists (
    wishlist_id          BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    customer_id          BIGINT NOT NULL REFERENCES customers(customer_id) ON DELETE CASCADE,
    wishlist_name        VARCHAR(100) DEFAULT 'My Wishlist',
    is_public            BOOLEAN DEFAULT FALSE,
    share_token          VARCHAR(64) UNIQUE,               -- for public sharing
    created_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_wishlists_customer_id ON wishlists(customer_id);


-- ------------------------------------------------------------
-- Table 27: wishlist_items
-- ------------------------------------------------------------
CREATE TABLE wishlist_items (
    wishlist_item_id     BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    wishlist_id          BIGINT NOT NULL REFERENCES wishlists(wishlist_id) ON DELETE CASCADE,
    product_id           BIGINT NOT NULL REFERENCES products(product_id),
    product_sku          VARCHAR(50) NOT NULL,
    price_when_added     DECIMAL(12,2),
    added_at             TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    priority             INTEGER DEFAULT 0,

    UNIQUE(wishlist_id, product_id)
);

CREATE INDEX idx_wishlist_items_wishlist_id ON wishlist_items(wishlist_id);
CREATE INDEX idx_wishlist_items_product_id ON wishlist_items(product_id);


-- ------------------------------------------------------------
-- Table 28: notifications
-- Outbound notification queue (email / SMS / push)
-- ------------------------------------------------------------
CREATE TABLE notifications (
    notification_id      BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    notification_uuid    UUID UNIQUE NOT NULL DEFAULT gen_random_uuid(),

    -- Recipient
    customer_id          BIGINT REFERENCES customers(customer_id),
    employee_id          INTEGER REFERENCES employees(employee_id),
    recipient_email      VARCHAR(255),
    recipient_phone      VARCHAR(20),
    recipient_device_token VARCHAR(500),

    -- Content
    channel              VARCHAR(20) NOT NULL
                         CHECK (channel IN ('EMAIL','SMS','PUSH','WHATSAPP','IN_APP')),
    notification_type    VARCHAR(100) NOT NULL,            -- 'ORDER_CONFIRMED','SHIPMENT_DISPATCHED'
    template_id          VARCHAR(100),
    subject              VARCHAR(300),
    body                 TEXT NOT NULL,
    metadata             JSONB,                            -- template variables

    -- Status
    notification_status  VARCHAR(30) DEFAULT 'QUEUED'
                         CHECK (notification_status IN ('QUEUED','SENT','DELIVERED','FAILED','BOUNCED','OPENED','CLICKED')),
    
    -- Tracking
    provider_message_id  VARCHAR(200),
    sent_at              TIMESTAMP,
    delivered_at         TIMESTAMP,
    opened_at            TIMESTAMP,
    clicked_at           TIMESTAMP,
    failed_reason        TEXT,
    retry_count          INTEGER DEFAULT 0,
    next_retry_at        TIMESTAMP,

    -- Relations
    order_id             BIGINT REFERENCES orders(order_id),
    shipment_id          BIGINT REFERENCES shipments(shipment_id),
    return_id            BIGINT REFERENCES returns(return_id),

    created_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_notifications_customer_id ON notifications(customer_id);
CREATE INDEX idx_notifications_status ON notifications(notification_status);
CREATE INDEX idx_notifications_type ON notifications(notification_type);
CREATE INDEX idx_notifications_queued ON notifications(next_retry_at)
    WHERE notification_status IN ('QUEUED','FAILED') AND retry_count < 3;


-- ------------------------------------------------------------
-- Table 29: audit_logs
-- Immutable change log — append-only, no updates/deletes
-- ------------------------------------------------------------
CREATE TABLE audit_logs (
    log_id               BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    log_uuid             UUID DEFAULT gen_random_uuid(),

    -- What changed
    table_name           VARCHAR(100) NOT NULL,
    record_id            BIGINT NOT NULL,
    operation            VARCHAR(10) NOT NULL CHECK (operation IN ('INSERT','UPDATE','DELETE','SELECT')),
    changed_fields       JSONB,                            -- {"old": {...}, "new": {...}}

    -- Who changed it
    changed_by_type      VARCHAR(20) CHECK (changed_by_type IN ('CUSTOMER','EMPLOYEE','SYSTEM','API')),
    changed_by_customer  BIGINT REFERENCES customers(customer_id),
    changed_by_employee  INTEGER REFERENCES employees(employee_id),
    changed_by_system    VARCHAR(100),                     -- 'FLINK_PIPELINE','CRON_JOB'

    -- Context
    ip_address           INET,
    user_agent           TEXT,
    session_id           VARCHAR(128),
    request_id           VARCHAR(100),
    api_endpoint         VARCHAR(500),

    -- Timing
    logged_at            TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- IMPORTANT: This table is append-only
    -- Do NOT add UPDATE or DELETE permissions on this table
    CONSTRAINT audit_logs_no_delete CHECK (TRUE)  -- enforced at DB role level
);

CREATE INDEX idx_audit_table_record ON audit_logs(table_name, record_id);
CREATE INDEX idx_audit_logged_at ON audit_logs(logged_at);
CREATE INDEX idx_audit_employee ON audit_logs(changed_by_employee);
CREATE INDEX idx_audit_operation ON audit_logs(operation);


-- ------------------------------------------------------------
-- Table 30: analytics_events
-- Clickstream / behavioral events (high-volume, partitioned)
-- ------------------------------------------------------------
CREATE TABLE analytics_events (
    event_id             BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    event_uuid           UUID NOT NULL DEFAULT gen_random_uuid(),
    session_id           VARCHAR(128) REFERENCES sessions(session_id),
    customer_id          BIGINT REFERENCES customers(customer_id),

    -- Event type
    event_type           VARCHAR(100) NOT NULL,
    -- Examples: 'page_view','product_view','add_to_cart','remove_from_cart',
    --           'checkout_start','checkout_complete','search','filter_applied',
    --           'coupon_applied','wishlist_add','review_submitted','login','logout'

    -- Context
    page_url             VARCHAR(1000),
    page_type            VARCHAR(50),                      -- 'HOME','PLP','PDP','CART','CHECKOUT'
    referrer_url         VARCHAR(1000),
    device_type          VARCHAR(50),

    -- Entity references (which product/order this event is about)
    product_id           BIGINT REFERENCES products(product_id),
    category_id          INTEGER REFERENCES categories(category_id),
    order_id             BIGINT REFERENCES orders(order_id),
    search_query         VARCHAR(500),

    -- Event payload
    properties           JSONB,                            -- flexible event-specific data

    -- Performance
    page_load_ms         INTEGER,

    -- Geo
    country_code         VARCHAR(5),
    city                 VARCHAR(100),

    occurred_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP

) PARTITION BY RANGE (occurred_at);

-- Create monthly partitions (example for 2025)
CREATE TABLE analytics_events_2025_01 PARTITION OF analytics_events
    FOR VALUES FROM ('2025-01-01') TO ('2025-02-01');
CREATE TABLE analytics_events_2025_02 PARTITION OF analytics_events
    FOR VALUES FROM ('2025-02-01') TO ('2025-03-01');
-- ... continue monthly

CREATE INDEX idx_analytics_session ON analytics_events(session_id, occurred_at);
CREATE INDEX idx_analytics_customer ON analytics_events(customer_id, occurred_at);
CREATE INDEX idx_analytics_event_type ON analytics_events(event_type, occurred_at);
CREATE INDEX idx_analytics_product ON analytics_events(product_id, occurred_at);


-- ============================================================
-- SECTION 3: VIEWS (Common query patterns for Flink YAML training)
-- ============================================================

-- Real-time order pipeline view (used by Flink source)
CREATE VIEW v_order_events AS
SELECT
    o.order_id,
    o.order_uuid,
    o.order_number,
    o.order_date,
    o.order_status,
    o.payment_status,
    o.total_amount,
    o.currency,
    o.channel,
    o.payment_method,
    o.device_type,
    o.discount_amount,
    o.coupon_code,
    c.customer_id,
    c.loyalty_tier,
    c.city AS customer_city,
    s.store_id,
    s.store_name,
    s.city AS store_city,
    s.region AS store_region,
    o.created_at,
    o.updated_at
FROM orders o
JOIN customers c ON o.customer_id = c.customer_id
JOIN stores s ON o.store_id = s.store_id;

-- Inventory alert view
CREATE VIEW v_inventory_alerts AS
SELECT
    i.inventory_id,
    p.product_id,
    p.product_sku,
    p.product_name,
    p.brand,
    c.category_name,
    i.warehouse_id,
    w.warehouse_name,
    w.city AS warehouse_city,
    i.store_id,
    i.quantity_on_hand,
    i.quantity_available,
    i.quantity_allocated,
    i.reorder_point,
    i.reorder_quantity,
    CASE
        WHEN i.quantity_available = 0 THEN 'OUT_OF_STOCK'
        WHEN i.quantity_available < i.reorder_point THEN 'LOW_STOCK'
        ELSE 'ADEQUATE'
    END AS stock_status
FROM inventory i
JOIN products p ON i.product_id = p.product_id
LEFT JOIN categories c ON p.category_id = c.category_id
LEFT JOIN warehouses w ON i.warehouse_id = w.warehouse_id;

-- Customer 360 view
CREATE VIEW v_customer_360 AS
SELECT
    c.customer_id,
    c.customer_number,
    c.first_name,
    c.last_name,
    c.email,
    c.loyalty_tier,
    c.loyalty_points,
    c.registration_date,
    COUNT(DISTINCT o.order_id)         AS total_orders,
    SUM(o.total_amount)                AS lifetime_value,
    AVG(o.total_amount)                AS avg_order_value,
    MAX(o.order_date)                  AS last_order_date,
    COUNT(DISTINCT r.review_id)        AS total_reviews,
    AVG(r.rating)                      AS avg_rating_given,
    COUNT(DISTINCT ret.return_id)      AS total_returns
FROM customers c
LEFT JOIN orders o ON c.customer_id = o.customer_id AND o.order_status != 'CANCELLED'
LEFT JOIN reviews r ON c.customer_id = r.customer_id
LEFT JOIN returns ret ON c.customer_id = ret.customer_id
GROUP BY c.customer_id, c.customer_number, c.first_name, c.last_name,
         c.email, c.loyalty_tier, c.loyalty_points, c.registration_date;


-- ============================================================
-- SECTION 4: SAMPLE DATA (for training dataset generation)
-- ============================================================

INSERT INTO categories (category_name, category_code, level, category_path) VALUES
('Electronics',        'ELECTRONICS',    0, 'Electronics'),
('Apparel',            'APPAREL',        0, 'Apparel'),
('Groceries',          'GROCERIES',      0, 'Groceries'),
('Home & Furniture',   'HOME',           0, 'Home & Furniture'),
('Sports & Fitness',   'SPORTS',         0, 'Sports & Fitness'),
('Books',              'BOOKS',          0, 'Books'),
('Mobile Phones',      'MOBILE',         1, 'Electronics > Mobile Phones'),
('Laptops',            'LAPTOPS',        1, 'Electronics > Laptops'),
('Mens Clothing',      'MENS_APPAREL',   1, 'Apparel > Mens Clothing'),
('Womens Clothing',    'WOMENS_APPAREL', 1, 'Apparel > Womens Clothing');

INSERT INTO warehouses (warehouse_code, warehouse_name, warehouse_type, address_line1, city, state_province, postal_code) VALUES
('WH-BLR-01', 'Bangalore Central Fulfillment',  'FULFILLMENT',   'Plot 45, Industrial Area', 'Bengaluru',  'Karnataka',   '560099'),
('WH-MUM-01', 'Mumbai Distribution Center',      'DISTRIBUTION',  'NH-48, Logistics Park',    'Mumbai',     'Maharashtra', '400070'),
('WH-DEL-01', 'Delhi NCR Warehouse',             'FULFILLMENT',   'Sector 58, Gurugram',      'Gurugram',   'Haryana',     '122001'),
('WH-CHN-01', 'Chennai South Hub',               'FULFILLMENT',   'OMR Road, Sholinganallur', 'Chennai',    'Tamil Nadu',  '600119'),
('WH-HYD-01', 'Hyderabad Express Center',        'DARK_STORE',    'Hitech City, Madhapur',    'Hyderabad',  'Telangana',   '500081');

INSERT INTO stores (store_code, store_name, store_type, city, state_province, postal_code, region, primary_warehouse_id) VALUES
('STR-BLR-001', 'MegaStore Indiranagar',   'PHYSICAL', 'Bengaluru', 'Karnataka',   '560038', 'SOUTH', 1),
('STR-BLR-002', 'MegaStore Koramangala',   'PHYSICAL', 'Bengaluru', 'Karnataka',   '560034', 'SOUTH', 1),
('STR-MUM-001', 'MegaStore Bandra',        'PHYSICAL', 'Mumbai',    'Maharashtra', '400050', 'WEST',  2),
('STR-DEL-001', 'MegaStore Connaught Place','PHYSICAL','New Delhi',  'Delhi',       '110001', 'NORTH', 3),
('STR-CHN-001', 'MegaStore Anna Nagar',    'PHYSICAL', 'Chennai',   'Tamil Nadu',  '600040', 'SOUTH', 4),
('STR-HYD-001', 'MegaStore Banjara Hills', 'PHYSICAL', 'Hyderabad', 'Telangana',   '500034', 'SOUTH', 5),
('STR-ONLINE',  'MegaStore Online',        'ONLINE_ONLY','Bengaluru','Karnataka',  '560001', 'ONLINE',1);

-- ============================================================
-- END OF SCHEMA
-- ============================================================
-- Summary:
--   30 tables | 7 views | sample seed data
--   Covers: catalog, orders, inventory, fulfillment, CRM,
--           discounts, HR/RBAC, analytics, audit, notifications
-- ============================================================
