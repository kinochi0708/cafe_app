from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
import os
from datetime import datetime
import pytz
from sqlalchemy import func, case

# Flaskアプリケーションの設定
app = Flask(__name__)

# データベースのファイルパスを設定
base_dir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.join(base_dir, "cafe_app.db")}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# 日本時間の取得関数
def get_jst_now():
    jst = pytz.timezone('Asia/Tokyo')
    return datetime.now(jst)

# データベースのテーブル定義（Productテーブル）
class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(200), nullable=True)
    category = db.Column(db.String(50), nullable=True)
    unitprice = db.Column(db.Float, nullable=False)

# データベースのテーブル定義（Userテーブル）
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), nullable=False)
    password = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(50), nullable=False)
    createdat = db.Column(db.DateTime, default=get_jst_now)

# データベースのテーブル定義（StockTransactionテーブル）
class StockTransaction(db.Model):
    __tablename__ = 'stocktransaction'

    id = db.Column(db.Integer, primary_key=True)
    productid = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    userid = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    type = db.Column(db.String(10), nullable=False)  # IN (入庫) or OUT (出庫)
    transactiondate = db.Column(db.DateTime, default=get_jst_now)
    notes = db.Column(db.String(200), nullable=True)

# 商品登録ページ
@app.route('/add_product', methods=['GET', 'POST'])
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
def products():
    products = Product.query.all()
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
    
    # 関連する在庫取引を削除
    StockTransaction.query.filter_by(productid=id).delete()

    try:
        db.session.delete(product)
        db.session.commit()
        return redirect(url_for('products'))
    except Exception as e:
        db.session.rollback()
        return f'エラーが発生しました: {str(e)}'

# 在庫の入出庫登録ページ
@app.route('/stock_transaction', methods=['GET', 'POST'])
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
def stock_transaction_list():
    transactions = StockTransaction.query.join(Product, StockTransaction.productid == Product.id) \
                                        .join(User, StockTransaction.userid == User.id) \
                                        .add_columns(
                                            StockTransaction.id,
                                            Product.name.label('product_name'),
                                            User.username.label('user_name'),
                                            StockTransaction.quantity,
                                            StockTransaction.type,
                                            StockTransaction.transactiondate,
                                            StockTransaction.notes
                                        ) \
                                        .order_by(StockTransaction.transactiondate.desc()) \
                                        .all()
    return render_template('stock_transaction_list.html', transactions=transactions)

# 在庫一覧ページ
@app.route('/stock_list')
def stock_list():
    stock_data = db.session.query(
        Product.id,
        Product.name.label('product_name'),
        (func.sum(case((StockTransaction.type == 'IN', StockTransaction.quantity), else_=0)) -
        func.sum(case((StockTransaction.type == 'OUT', StockTransaction.quantity), else_=0))
        ).label('total_quantity'),
        func.max(StockTransaction.transactiondate).label('last_updated')
    ).outerjoin(StockTransaction, Product.id == StockTransaction.productid) \
    .group_by(Product.id, Product.name).all()

    stock_list = [
        {
            'id': stock.id,
            'product_name': stock.product_name,
            'total_quantity': stock.total_quantity if stock.total_quantity is not None else 0,
            'last_updated': stock.last_updated.strftime('%Y-%m-%d %H:%M:%S') if stock.last_updated else '未更新'
        }
        for stock in stock_data
    ]

    return render_template('stock_list.html', stock_list=stock_list)

# アプリケーションの起動
if __name__ == '__main__':
    app.run(debug=True)
