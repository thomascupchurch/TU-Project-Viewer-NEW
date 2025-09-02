import os
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, send_file
from flask_login import login_required, current_user
from db import db, ContactDB, AssetDB

resources_bp = Blueprint('resources', __name__)

@resources_bp.route('/resources', methods=['GET', 'POST'])
@login_required
def resources_page():
    asset_dir = os.path.join(resources_bp.root_path, 'static', 'assets')
    os.makedirs(asset_dir, exist_ok=True)
    if request.method == 'POST':
        form_type = request.form.get('form_type')
        if form_type == 'contact':
            name = request.form.get('name','').strip()
            if name:
                c = ContactDB(
                    user_id=current_user.get_id(),
                    name=name,
                    title=request.form.get('title','').strip(),
                    company=request.form.get('company','').strip(),
                    email=request.form.get('email','').strip(),
                    phone=request.form.get('phone','').strip(),
                    address=request.form.get('address','').strip(),
                    notes=request.form.get('notes','').strip(),
                )
                db.session.add(c); db.session.commit()
                flash('Contact added.')
            return redirect(url_for('resources.resources_page'))
        elif form_type == 'asset':
            f = request.files.get('asset_file')
            if f and f.filename:
                safe_name = f.filename.replace('..','').replace('/','_').replace('\\','_')
                save_path = os.path.join(asset_dir, safe_name)
                f.save(save_path)
                size_bytes = os.path.getsize(save_path) if os.path.exists(save_path) else 0
                a = AssetDB(
                    user_id=current_user.get_id(),
                    filename=safe_name,
                    original_name=f.filename,
                    description=request.form.get('description','').strip(),
                    size_bytes=size_bytes
                )
                db.session.add(a); db.session.commit()
                flash('Asset uploaded.')
            return redirect(url_for('resources.resources_page'))
    contacts = ContactDB.query.order_by(ContactDB.created_at.desc()).all()
    assets = AssetDB.query.order_by(AssetDB.created_at.desc()).all()
    def human(n):
        for unit in ['B','KB','MB','GB']:
            if n < 1024.0:
                return f"{n:3.1f} {unit}"
            n /= 1024.0
        return f"{n:.1f} TB"
    assets_view = []
    for a in assets:
        assets_view.append(type('AV',(),{
            'id': a.id,
            'filename': a.filename,
            'description': a.description,
            'size_human': human(a.size_bytes or 0),
            'created_at': a.created_at
        }))
    return render_template('resources.html', contacts=contacts, assets=assets_view)

@resources_bp.route('/delete_contact', methods=['POST'])
@login_required
def delete_contact():
    cid = request.form.get('contact_id')
    if cid and cid.isdigit():
        c = ContactDB.query.get(int(cid))
        if c:
            if c.user_id == current_user.get_id() or getattr(current_user,'is_admin',False):
                db.session.delete(c); db.session.commit(); flash('Contact deleted.')
            else:
                flash('Not authorized to delete this contact.')
    return redirect(url_for('resources.resources_page'))

@resources_bp.route('/download_asset/<int:asset_id>')
@login_required
def download_asset(asset_id):
    asset_dir = os.path.join(resources_bp.root_path, 'static', 'assets')
    a = AssetDB.query.get(asset_id)
    if not a:
        abort(404)
    if a.user_id != current_user.get_id() and not getattr(current_user,'is_admin',False):
        abort(403)
    path = os.path.join(asset_dir, a.filename)
    if not os.path.exists(path):
        abort(404)
    return send_file(path, as_attachment=True, download_name=a.original_name or a.filename)

@resources_bp.route('/delete_asset', methods=['POST'])
@login_required
def delete_asset():
    aid = request.form.get('asset_id')
    asset_dir = os.path.join(resources_bp.root_path, 'static', 'assets')
    if aid and aid.isdigit():
        a = AssetDB.query.get(int(aid))
        if a:
            if a.user_id == current_user.get_id() or getattr(current_user,'is_admin',False):
                filepath = os.path.join(asset_dir, a.filename)
                try:
                    if os.path.exists(filepath):
                        os.remove(filepath)
                except Exception:
                    pass
                db.session.delete(a); db.session.commit(); flash('Asset deleted.')
            else:
                flash('Not authorized to delete this asset.')
    return redirect(url_for('resources.resources_page'))