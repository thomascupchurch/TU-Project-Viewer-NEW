from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from . import db, Item

items_bp = Blueprint('items', __name__, url_prefix='/items')

@items_bp.route('/')
@login_required
def list_items():
    items = Item.query.filter_by(user_id=current_user.id).order_by(Item.created_at.desc()).all()
    return render_template('items.html', items=items)

@items_bp.post('/create')
@login_required
def create_item():
    name = request.form.get('title','').strip()
    if not name:
        flash('Title required')
        return redirect(url_for('items.list_items'))
    itm = Item(name=name, user_id=current_user.id)
    db.session.add(itm)
    db.session.commit()
    flash('Item created')
    return redirect(url_for('items.list_items'))

@items_bp.post('/<int:item_id>/update')
@login_required
def update_item(item_id: int):
    itm = Item.query.get_or_404(item_id)
    if itm.user_id != current_user.id:
        flash('Not allowed')
        return redirect(url_for('items.list_items'))
    name = request.form.get('title','').strip()
    if name:
        itm.name = name
        db.session.commit()
        flash('Updated')
    else:
        flash('Title cannot be empty')
    return redirect(url_for('items.list_items'))

@items_bp.post('/<int:item_id>/delete')
@login_required
def delete_item(item_id: int):
    itm = Item.query.get_or_404(item_id)
    if itm.user_id != current_user.id:
        flash('Not allowed')
        return redirect(url_for('items.list_items'))
    db.session.delete(itm)
    db.session.commit()
    flash('Deleted')
    return redirect(url_for('items.list_items'))
