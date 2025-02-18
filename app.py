from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import os
from datetime import datetime
import pytz
from sqlalchemy import func, case

# Flaskアプリケーションの設定
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///cafe_app.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'your_secret_key'  # セッション管理用の秘密鍵

# データベースのファイルパスを設定
base_dir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.join(base_dir, "cafe_app.db")}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'  # 未ログイン時にリダイレクトするページ

# 日本時間の取得関数（マイクロ秒を切り捨て）
def get_jst_now():
    jst = pytz.timezone('Asia/Tokyo')
    now = datetime.now().replace(microsecond=0)  # naive datetime を生成
    now_jst = jst.localize(now)  # JST のタイムゾーンを付与
    return now_jst.strftime('%Y-%m-%d %H:%M:%S')  # SQLite に保存するフォーマットに変換


# データベースのテーブル定義（Productテーブル）
class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(200), nullable=True)
    category = db.Column(db.String(50), nullable=True)
    unitprice = db.Column(db.Float, nullable=False)
    deleted = db.Column(db.Boolean, default=False)  # 削除フラグ追加

# データベースのテーブル定義（Userテーブル）
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), nullable=False, unique=True)
    password = db.Column(db.String(100), nullable=False)  # パスワードをそのまま保存（非推奨）
    role = db.Column(db.String(50), nullable=False)
    createdat = db.Column(db.String, default=lambda: get_jst_now())

# データベースのテーブル定義（StockTransactionテーブル）
class StockTransaction(db.Model):
    __tablename__ = 'stocktransaction'

    id = db.Column(db.Integer, primary_key=True)
    productid = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    userid = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    type = db.Column(db.String(10), nullable=False)  # 'IN' (入庫) or 'OUT' (出庫)
    transactiondate = db.Column(db.String, default=lambda: get_jst_now())
    notes = db.Column(db.String(200), nullable=True)
    deleted = db.Column(db.Boolean, default=False)  # 論理削除用フラグを追加

# Flask-Login用のユーザー情報取得
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ログインページ
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()

        if user and user.password == password:  # パスワードをそのまま比較
            login_user(user)
            return redirect(url_for('stock_list'))
        else:
            flash('ログインに失敗しました。ユーザー名またはパスワードが間違っています。', 'danger')

    return render_template('login.html')

# ログアウト機能
@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# ユーザー登録（登録後、ログインページに遷移）
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']  # そのまま保存（非推奨）
        role = request.form['role']

        new_user = User(username=username, password=password, role=role)
        db.session.add(new_user)
        db.session.commit()

        return redirect(url_for('login'))  # 登録後にログインページへリダイレクト

    return render_template('register.html')

# 商品登録ページ
@app.route('/add_product', methods=['GET', 'POST'])
@login_required
def add_product():
    if request.method == 'POST':
        name = request.form['name']
        description = request.form['description']
        category = request.form['category']
        unitprice = request.form['unitprice']

        new_product = Product(
            name=name,
            description=description,
            category=category,
            unitprice=float(unitprice)
        )

        try:
            db.session.add(new_product)
            db.session.commit()
            return redirect(url_for('add_product'))
        except Exception as e:
            db.session.rollback()
            return f'エラーが発生しました: {str(e)}'

    return render_template('add_product.html')

# 商品一覧ページ
@app.route('/products')
@login_required
def products():
    products = Product.query.filter_by(deleted=False).all()  # 削除フラグが False のもののみ取得
    return render_template('products.html', products=products)

# 商品編集ページ
@app.route('/edit_product/<int:id>', methods=['GET', 'POST'])
def edit_product(id):
    product = Product.query.get_or_404(id)

    if request.method == 'POST':
        product.name = request.form['name']
        product.description = request.form['description']
        product.category = request.form['category']
        product.unitprice = float(request.form['unitprice'])

        try:
            db.session.commit()
            return redirect(url_for('products'))
        except Exception as e:
            db.session.rollback()
            return f'エラーが発生しました: {str(e)}'

    return render_template('edit_product.html', product=product)

# 商品削除ページ
@app.route('/delete_product/<int:id>', methods=['POST'])
def delete_product(id):
    product = Product.query.get_or_404(id)

    try:
        product.deleted = True  # 削除フラグを True に設定
        db.session.commit()
        return redirect(url_for('products'))
    except Exception as e:
        db.session.rollback()
        return f'エラーが発生しました: {str(e)}'

# 在庫の入出庫登録ページ
@app.route('/stock_transaction', methods=['GET', 'POST'])
@login_required
def stock_transaction():
    products = Product.query.all()
    users = User.query.all()

    if request.method == 'POST':
        productid = request.form['productid']
        userid = request.form['userid']
        quantity = int(request.form['quantity'])
        transaction_type = 'IN' if request.form['type'] == '入庫' else 'OUT'
        notes = request.form.get('notes', '')

        new_transaction = StockTransaction(
            productid=productid,
            userid=userid,
            quantity=quantity,
            type=transaction_type,
            notes=notes
        )

        try:
            db.session.add(new_transaction)
            db.session.commit()
            return redirect(url_for('stock_transaction'))
        except Exception as e:
            db.session.rollback()
            return f'エラーが発生しました: {str(e)}'

    return render_template('stock_transaction.html', products=products, users=users)

# 在庫の入出庫履歴一覧ページ
@app.route('/stock_transaction_list')
@login_required
def stock_transaction_list():
    transactions = StockTransaction.query.join(Product, StockTransaction.productid == Product.id, isouter=True) \
                                        .join(User, StockTransaction.userid == User.id) \
                                        .add_columns(
                                            StockTransaction.id,
                                            case(
                                                (Product.deleted == True, Product.name),  
                                                else_=Product.name
                                            ).label('product_name'),
                                            User.username.label('user_name'),
                                            StockTransaction.quantity,
                                            StockTransaction.type,
                                            StockTransaction.transactiondate,
                                            StockTransaction.notes,
                                            Product.deleted.label('product_deleted'),
                                            StockTransaction.deleted.label('transaction_deleted')  # ★ 追加
                                        ) \
                                        .order_by(StockTransaction.transactiondate.desc()) \
                                        .all()
    return render_template('stock_transaction_list.html', transactions=transactions)

# 在庫の入出庫履歴編集ページ
@app.route('/edit_stock_transaction/<int:id>', methods=['GET', 'POST'])
def edit_stock_transaction(id):
    transaction = StockTransaction.query.get_or_404(id)
    products = Product.query.all()
    users = User.query.all()

    if request.method == 'POST':
        transaction.productid = request.form['productid']
        transaction.userid = request.form['userid']
        transaction.quantity = int(request.form['quantity'])
        transaction.type = 'IN' if request.form['type'] == '入庫' else 'OUT'
        transaction.notes = request.form.get('notes', '')

        try:
            db.session.commit()
            return redirect(url_for('stock_transaction_list'))
        except Exception as e:
            db.session.rollback()
            return f'エラーが発生しました: {str(e)}'

    return render_template('edit_stock_transaction.html', transaction=transaction, products=products, users=users)

# 在庫の入出庫履歴削除ページ
@app.route('/delete_stock_transaction/<int:id>', methods=['POST'])
def delete_stock_transaction(id):
    transaction = StockTransaction.query.get_or_404(id)

    try:
        transaction.deleted = True  # 論理削除
        db.session.commit()
        return redirect(url_for('stock_transaction_list'))
    except Exception as e:
        db.session.rollback()
        return f'エラーが発生しました: {str(e)}'

# 在庫一覧ページ
@app.route('/stock_list')
@login_required
def stock_list():
    stock_data = db.session.query(
        Product.id,
        Product.name.label('product_name'),
        (func.sum(case((StockTransaction.type == 'IN', StockTransaction.quantity), else_=0)) -
        func.sum(case((StockTransaction.type == 'OUT', StockTransaction.quantity), else_=0))
        ).label('total_quantity'),
        func.max(StockTransaction.transactiondate).label('last_updated')
    ).outerjoin(StockTransaction, Product.id == StockTransaction.productid) \
    .filter(Product.deleted == False) \
    .group_by(Product.id, Product.name) \
    .all()

    stock_list = []
    for stock in stock_data:
        if stock.last_updated:
            try:
                last_updated_dt = datetime.strptime(stock.last_updated, '%Y-%m-%d %H:%M:%S')
            except ValueError:
                last_updated_str = '未更新'
            else:
                last_updated_str = last_updated_dt.strftime('%Y-%m-%d %H:%M:%S')
        else:
            last_updated_str = '未更新'
        
        stock_list.append({
            'id': stock.id,
            'product_name': stock.product_name,
            'total_quantity': stock.total_quantity if stock.total_quantity is not None else 0,
            'last_updated': last_updated_str
        })

    return render_template('stock_list.html', stock_list=stock_list)

# アプリケーションの起動
if __name__ == '__main__':
    app.run(debug=True)
