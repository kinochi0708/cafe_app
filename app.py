from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
import os

# Flaskアプリケーションの設定
app = Flask(__name__)

# データベースのファイルパスを設定
base_dir = os.path.abspath(os.path.dirname(__file__))  # カレントディレクトリを取得
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.join(base_dir, "cafe_app.db")}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# データベースのテーブル定義（Productテーブル）
class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(200), nullable=True)
    category = db.Column(db.String(50), nullable=True)
    unitprice = db.Column(db.Float, nullable=False)  # unit_price から unitprice に変更

# 商品登録画面のルート
@app.route('/add_product', methods=['GET', 'POST'])
def add_product():
    if request.method == 'POST':
        name = request.form['name']
        description = request.form['description']
        category = request.form['category']
        unitprice = request.form['unitprice']  # フォームから送信された unit_price の値を unitprice に変更

        # 受け取ったデータを表示して確認
        print(f"商品名: {name}, 説明: {description}, カテゴリ: {category}, 単価: {unitprice}")

        new_product = Product(
            name=name,
            description=description,
            category=category,
            unitprice=float(unitprice)  # unit_price を unitprice に変更
        )

        try:
            db.session.add(new_product)
            db.session.commit()  # これでデータベースに変更を反映させる
            return redirect(url_for('add_product'))  # 商品登録後に再度登録画面を表示
        except Exception as e:
            db.session.rollback()  # エラーが発生した場合はロールバック
            return f'エラーが発生しました: {str(e)}'

    return render_template('add_product.html')

# 在庫一覧ページのルート
@app.route('/inventory')
def inventory():
    # データベースから全ての商品を取得
    products = Product.query.all()
    return render_template('inventory.html', products=products)

# アプリケーションの起動
if __name__ == '__main__':
    app.run(debug=True)
