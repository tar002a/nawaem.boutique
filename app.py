import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import pytz
import psycopg2
import time

# --- إعداد الصفحة (يجب أن يكون أول سطر) ---
st.set_page_config(page_title="Nawaem POS 2.0", layout="wide", page_icon="🛍️", initial_sidebar_state="collapsed")

# --- CSS وتصميم UI متطور ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@300;400;600;700;800&display=swap');
    
    :root {
        --primary: #B76E79;
        --primary-hover: #D4A5A5;
        --bg-dark: #121212;
        --card-bg: #1E1E1E;
        --text-main: #FFFFFF;
        --text-sub: #A0A0A0;
        --success: #4CAF50;
        --border: #333333;
    }

    /* تطبيق الخط والاتجاه */
    * {
        font-family: 'Cairo', sans-serif !important;
        box-sizing: border-box;
    }
    
    .stApp {
        background-color: var(--bg-dark);
        direction: rtl;
    }

    /* تحسين الأزرار */
    .stButton button {
        border-radius: 12px !important;
        font-weight: 700 !important;
        transition: all 0.2s ease-in-out !important;
        border: none !important;
        height: 45px;
    }
    
    /* زر الإضافة للسلة */
    .add-btn button {
        background-color: var(--primary) !important;
        color: white !important;
        width: 100%;
    }
    .add-btn button:hover {
        background-color: var(--primary-hover) !important;
        transform: scale(1.02);
    }

    /* بطاقات المنتجات */
    .product-card {
        background-color: var(--card-bg);
        border: 1px solid var(--border);
        border-radius: 16px;
        padding: 15px;
        text-align: center;
        transition: transform 0.2s;
        height: 100%;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
    }
    .product-card:hover {
        border-color: var(--primary);
        transform: translateY(-5px);
        box-shadow: 0 4px 20px rgba(0,0,0,0.3);
    }
    .price-tag {
        font-size: 1.2rem;
        font-weight: 800;
        color: var(--primary);
        margin: 8px 0;
    }
    .stock-tag {
        font-size: 0.8rem;
        color: var(--text-sub);
        background: #2c2c2e;
        padding: 2px 8px;
        border-radius: 8px;
    }

    /* سلة المشتريات */
    .cart-container {
        background-color: #1A1A1A;
        border-left: 1px solid var(--border);
        padding: 20px;
        border-radius: 16px;
        height: 80vh;
        overflow-y: auto;
    }
    
    /* تحسين المدخلات */
    .stTextInput input, .stNumberInput input {
        background-color: #2C2C2E !important;
        border: 1px solid var(--border) !important;
        color: white !important;
        border-radius: 10px !important;
    }

    /* إخفاء القوائم الافتراضية المزعجة */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    
</style>
""", unsafe_allow_html=True)

# --- إدارة الحالة (Session State) ---
if 'cart' not in st.session_state: st.session_state.cart = {}
if 'last_invoice' not in st.session_state: st.session_state.last_invoice = None

# --- دوال قاعدة البيانات (Backend Logic) ---
@st.cache_resource
def init_connection():
    return psycopg2.connect(**st.secrets["postgres"])

def run_query(query, params=None, fetch_df=False):
    """دالة مركزية لتنفيذ الاستعلامات بأمان"""
    conn = None
    try:
        conn = init_connection()
        if fetch_df:
            return pd.read_sql(query, conn, params=params)
        else:
            with conn.cursor() as cur:
                cur.execute(query, params)
                if query.strip().upper().startswith("SELECT") or "RETURNING" in query.strip().upper():
                    return cur.fetchall()
                conn.commit()
                return True
    except Exception as e:
        if conn: conn.rollback()
        st.error(f"DB Error: {e}")
        return None

# دالة ذكية للبحث داخل قاعدة البيانات (سريعة جداً)
def search_products_sql(search_term, limit=50):
    if not search_term:
        q = "SELECT id, name, color, size, price, stock FROM public.variants WHERE stock > 0 ORDER BY id DESC LIMIT %s"
        return run_query(q, (limit,), fetch_df=True)
    else:
        # استخدام ILIKE للبحث غير الحساس لحالة الأحرف
        search_pattern = f"%{search_term}%"
        q = """
            SELECT id, name, color, size, price, stock 
            FROM public.variants 
            WHERE stock > 0 AND (name ILIKE %s OR color ILIKE %s OR size ILIKE %s)
            LIMIT %s
        """
        return run_query(q, (search_pattern, search_pattern, search_pattern, limit), fetch_df=True)

# --- واجهة المستخدم (UI Components) ---

def render_pos_tab():
    """واجهة نقطة البيع المحسنة"""
    col_products, col_cart = st.columns([3, 1.2]) # تقسيم الشاشة: منتجات (كبير) وسلة (صغير)

    # === القسم الأيمن: المنتجات ===
    with col_products:
        # شريط البحث العلوي
        c1, c2 = st.columns([4, 1])
        search_txt = c1.text_input("🔍 بحث سريع (اسم، لون، قياس)...", key="pos_search", label_visibility="collapsed")
        c2.markdown(f"<div style='text-align:center; padding-top:10px; color:#666'>نتائج البحث</div>", unsafe_allow_html=True)
        
        # جلب البيانات من السيرفر مباشرة
        df = search_products_sql(search_txt, limit=30)
        
        if not df.empty:
            # عرض شبكي (Grid Layout)
            cols = st.columns(3) # 3 منتجات في الصف
            for idx, row in df.iterrows():
                # تدوير الأعمدة لعمل Grid
                with cols[idx % 3]:
                    # تصميم البطاقة
                    st.markdown(f"""
                    <div class="product-card">
                        <div style="font-weight:700; font-size:1.1em; margin-bottom:5px;">{row['name']}</div>
                        <div style="font-size:0.9em; color:#ccc;">{row['color']} | {row['size']}</div>
                        <div class="price-tag">{row['price']:,.0f} د.ع</div>
                        <div class="stock-tag">متوفر: {row['stock']}</div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # زر الإضافة (منفصل عن HTML ليعمل مع Streamlit)
                    # مفتاح فريد لكل زر
                    if st.button("➕ أضف", key=f"add_{row['id']}", type="secondary", use_container_width=True):
                        add_to_cart(row)
                    
                    st.markdown("<div style='margin-bottom:15px'></div>", unsafe_allow_html=True)
        else:
            st.info("لا توجد منتجات مطابقة")

    # === القسم الأيسر: سلة المشتريات (Sticky Cart) ===
    with col_cart:
        with st.container(border=True):
            st.markdown("### 🛒 السلة")
            if not st.session_state.cart:
                st.caption("السلة فارغة")
            else:
                total_cart = 0
                for pid, item in list(st.session_state.cart.items()):
                    total_item = item['price'] * item['qty']
                    total_cart += total_item
                    
                    # عنصر السلة المصغر
                    c_info, c_del = st.columns([4, 1])
                    with c_info:
                        st.markdown(f"**{item['name']}** <span style='font-size:0.8em; color:#aaa'>({item['color']}-{item['size']})</span>", unsafe_allow_html=True)
                        cc1, cc2 = st.columns(2)
                        new_qty = cc1.number_input("العدد", 1, int(item['max_stock']), int(item['qty']), key=f"qty_{pid}", label_visibility="collapsed")
                        cc2.markdown(f"<div style='padding-top:5px; color:#B76E79; font-weight:bold'>{total_item:,.0f}</div>", unsafe_allow_html=True)
                        
                        # تحديث الكمية
                        if new_qty != item['qty']:
                            st.session_state.cart[pid]['qty'] = new_qty
                            st.rerun()

                    with c_del:
                        if st.button("❌", key=f"del_{pid}"):
                            del st.session_state.cart[pid]
                            st.rerun()
                    
                    st.divider()

                # ملخص السلة
                st.markdown(f"""
                <div style="background:#2C2C2E; padding:15px; border-radius:10px; text-align:center; margin-top:20px;">
                    <div style="color:#aaa;">الإجمالي</div>
                    <div style="font-size:1.8em; color:#B76E79; font-weight:bold;">{total_cart:,.0f}</div>
                </div>
                """, unsafe_allow_html=True)

                # نموذج العميل والدفع
                with st.form("checkout_form"):
                    st.markdown("##### بيانات العميل")
                    cust_name = st.text_input("اسم العميل / انستغرام")
                    cust_phone = st.text_input("رقم الهاتف", placeholder="07xxxxxxxxx")
                    cust_addr = st.text_input("العنوان")
                    delivery_days = st.selectbox("التوصيل خلال", ["24 ساعة", "48 ساعة", "3 أيام", "أسبوع"], index=1)
                    
                    if st.form_submit_button("✅ إتمام البيع", type="primary"):
                        process_checkout(cust_name, cust_phone, cust_addr, delivery_days)

def add_to_cart(row):
    """إضافة منتج للسلة بذكاء"""
    pid = row['id']
    if pid in st.session_state.cart:
        if st.session_state.cart[pid]['qty'] < row['stock']:
            st.session_state.cart[pid]['qty'] += 1
            st.toast(f"تم زيادة الكمية: {row['name']}", icon="➕")
        else:
            st.toast("الكمية المطلوبة غير متوفرة!", icon="⚠️")
    else:
        st.session_state.cart[pid] = {
            'id': row['id'],
            'name': row['name'],
            'color': row['color'],
            'size': row['size'],
            'price': float(row['price']),
            'max_stock': row['stock'],
            'qty': 1
        }
        st.toast("تمت الإضافة للسلة", icon="🛒")

def process_checkout(name, phone, addr, duration):
    """معالجة البيع (Transaction)"""
    if not name or not st.session_state.cart:
        st.error("يرجى ملء اسم العميل والتأكد من وجود منتجات")
        return

    try:
        conn = init_connection()
        with conn.cursor() as cur:
            # 1. إنشاء العميل أو تحديثه
            cur.execute("INSERT INTO public.customers (name, phone, address, username) VALUES (%s, %s, %s, %s) RETURNING id", 
                        (name, phone, addr, name))
            cust_id = cur.fetchone()[0]
            
            # 2. التوقيت
            tz = pytz.timezone('Asia/Baghdad')
            now = datetime.now(tz)
            inv_id = now.strftime("%Y%m%d%H%M")
            
            invoice_text = f"🌸 فاتورة طلب ({inv_id})\nالاسم: {name}\n---\n"

            # 3. إدخال المبيعات وتحديث المخزون
            for pid, item in st.session_state.cart.items():
                # جلب التكلفة للحساب الدقيق للربح
                cur.execute("SELECT cost FROM public.variants WHERE id = %s", (pid,))
                cost = cur.fetchone()[0]
                profit = (item['price'] - cost) * item['qty']
                total_line = item['price'] * item['qty']
                
                # خصم المخزون
                cur.execute("UPDATE public.variants SET stock = stock - %s WHERE id = %s", (item['qty'], pid))
                
                # تسجيل البيع
                cur.execute("""
                    INSERT INTO public.sales 
                    (customer_id, variant_id, product_name, qty, total, profit, date, invoice_id, delivery_duration)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (cust_id, pid, item['name'], item['qty'], total_line, profit, now, inv_id, duration))
                
                invoice_text += f"▫️ {item['name']} | {item['color']} ({item['size']}) x {item['qty']} = {total_line:,.0f}\n"

            conn.commit()
            
            # نجاح
            st.session_state.cart = {} # تفريغ السلة
            st.session_state.last_invoice = invoice_text
            st.success("تم تسجيل الطلب بنجاح! 🎉")
            st.balloons()
            st.rerun() # تحديث الصفحة لتحديث المخزون المعروض

    except Exception as e:
        if conn: conn.rollback()
        st.error(f"فشلت العملية: {e}")

# --- باقي التبويبات (مخزون / تقارير) ---

def render_inventory_tab():
    st.markdown("### 📦 إدارة المخزون السريعة")
    
    col_search, col_add = st.columns([3, 1])
    with col_search:
        q = st.text_input("بحث في المخزون...", key="inv_search")
    with col_add:
        # زر لإضافة منتج (مبسط)
        if st.button("➕ إضافة صنف جديد", type="primary", use_container_width=True):
             add_product_dialog()

    # عرض البيانات باستخدام Pagination
    page_size = 20
    if 'page' not in st.session_state: st.session_state.page = 0
    
    offset = st.session_state.page * page_size
    
    # استعلام SQL مع OFFSET
    if q:
        query = f"SELECT * FROM public.variants WHERE name ILIKE %s OR color ILIKE %s ORDER BY id DESC LIMIT {page_size} OFFSET {offset}"
        params = (f"%{q}%", f"%{q}%")
    else:
        query = f"SELECT * FROM public.variants ORDER BY id DESC LIMIT {page_size} OFFSET {offset}"
        params = None
        
    df = run_query(query, params, fetch_df=True)
    
    if not df.empty:
        # استخدام Data Editor للتعديل المباشر السريع
        edited_df = st.data_editor(
            df,
            column_config={
                "id": st.column_config.NumberColumn("ID", disabled=True),
                "name": "الاسم",
                "color": "اللون",
                "size": "القياس",
                "stock": st.column_config.NumberColumn("العدد", min_value=0),
                "price": st.column_config.NumberColumn("سعر البيع", format="%d"),
                "cost": st.column_config.NumberColumn("التكلفة", format="%d"),
            },
            hide_index=True,
            use_container_width=True,
            key="inv_editor"
        )
        
        # كشف التعديلات وحفظها
        # (ملاحظة: هذا يتطلب منطقاً إضافياً للتعامل مع session_state للحفظ الفعلي، 
        # ولكن هنا سنضع زر حفظ بسيط للتوضيح)
        if st.button("💾 حفظ التعديلات الجماعية"):
            # هنا يمكنك مقارنة df الأصلي مع edited_df وتحديث قاعدة البيانات
            # للتبسيط، سنفترض أن المستخدم يعدل صفاً بصف عبر dialog منفصل أفضل للأداء
            st.warning("للحصول على أفضل أداء، استخدم التعديل الفردي أو قم بتفعيل زر الحفظ المجمع.")
            
    # أزرار التنقل
    c_prev, c_next = st.columns([1, 1])
    if c_prev.button("السابق") and st.session_state.page > 0:
        st.session_state.page -= 1
        st.rerun()
    if c_next.button("التالي") and len(df) == page_size:
        st.session_state.page += 1
        st.rerun()

@st.dialog("إضافة منتج")
def add_product_dialog():
    with st.form("new_prod"):
        name = st.text_input("الاسم")
        c1, c2 = st.columns(2)
        color = c1.text_input("اللون")
        size = c2.text_input("القياس")
        c3, c4, c5 = st.columns(3)
        stock = c3.number_input("العدد", 1)
        price = c4.number_input("سعر البيع", 0.0)
        cost = c5.number_input("التكلفة", 0.0)
        
        if st.form_submit_button("حفظ"):
            run_query("INSERT INTO public.variants (name, color, size, stock, price, cost) VALUES (%s,%s,%s,%s,%s,%s)", 
                      (name, color, size, stock, price, cost))
            st.rerun()

@st.cache_data(ttl=300) # تخزين الكاش لمدة 5 دقائق
def get_dashboard_metrics():
    """جلب الإحصائيات مرة واحدة كل 5 دقائق لتخفيف الحمل"""
    conn = init_connection()
    # استعلام واحد لجلب كل الأرقام المهمة
    q = """
        SELECT 
            (SELECT COALESCE(SUM(total), 0) FROM public.sales WHERE date >= CURRENT_DATE) as sales_today,
            (SELECT COUNT(*) FROM public.sales WHERE date >= CURRENT_DATE) as orders_today,
            (SELECT COALESCE(SUM(profit), 0) FROM public.sales WHERE date >= CURRENT_DATE) as profit_today,
            (SELECT COALESCE(SUM(amount), 0) FROM public.expenses WHERE date >= CURRENT_DATE) as exp_today
    """
    df = pd.read_sql(q, conn)
    return df.iloc[0]

def render_dashboard_tab():
    st.markdown("### 📊 لوحة المعلومات (Live)")
    
    # جلب البيانات من الكاش
    metrics = get_dashboard_metrics()
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("مبيعات اليوم", f"{metrics['sales_today']:,.0f}", f"{metrics['orders_today']} طلب")
    c2.metric("صافي الربح", f"{metrics['profit_today'] - metrics['exp_today']:,.0f}")
    c3.metric("مصاريف اليوم", f"{metrics['exp_today']:,.0f}")
    
    # يمكن إضافة رسوم بيانية بسيطة هنا
    st.info("يتم تحديث هذه الأرقام تلقائياً كل 5 دقائق لتحسين السرعة.")

# --- التطبيق الرئيسي ---
def main():
    # القائمة الجانبية للتنقل
    with st.sidebar:
        st.image("https://cdn-icons-png.flaticon.com/512/3144/3144456.png", width=100)
        st.markdown("### نواعم سيستم")
        selected_tab = st.radio("القائمة", ["🛒 نقطة البيع", "📦 المخزن", "📊 التقارير", "↩️ الرواجع"], label_visibility="collapsed")
        st.divider()
        if st.button("تحديث البيانات 🔄"):
            st.cache_data.clear()
            st.rerun()

    # التوجيه حسب التبويب المختار
    if selected_tab == "🛒 نقطة البيع":
        render_pos_tab()
    elif selected_tab == "📦 المخزن":
        render_inventory_tab()
    elif selected_tab == "📊 التقارير":
        render_dashboard_tab()
    elif selected_tab == "↩️ الرواجع":
        st.markdown("### 🚧 قيد التطوير في النسخة السريعة")
        st.info("يمكنك استخدام الكود السابق للرواجع، لكن يفضل تحويله لنظام SQL المباشر.")

if __name__ == "__main__":
    # تشغيل التطبيق
    main()
