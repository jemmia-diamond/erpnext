frappe.provide('erpnext.utils.sales_order_gallery');

$.extend(erpnext.utils.sales_order_gallery, {
	bind_gallery_listeners(frm) {
		if (frm.__gallery_bound) return;
		frm.__gallery_bound = true;

		const $grid = frm.fields_dict?.items?.grid?.wrapper;
		if ($grid && $grid.length) {
			const rerender = frappe.utils.debounce(() => erpnext.utils.sales_order_gallery.render_gallery(frm), 400);
			$grid.on('change', 'input,select,textarea', rerender);
			$grid.on('click', '.grid-remove-rows, .grid-delete-row', rerender);
			$grid.on('click', '.grid-add-row, .grid-insert-row, .grid-insert-row-below', rerender);
			$grid.on('grid-row-render', rerender);
		}
	},

	async render_gallery(frm) {
		const fld = frm.get_field('custom_all_images_html');
		if (!fld) return;

		const $wrap = fld.$wrapper;
		$wrap.empty();

		if (!$wrap.find('style[data-so-gallery]').length) {
			$wrap.append(`
				<style data-so-gallery>
					.so-gallery{ display:flex; flex-wrap:wrap; gap:10px; }
					.so-gallery .img{
						width:140px; aspect-ratio:1/1; overflow:hidden;
						border:1px solid var(--border-color, #e5e7eb); border-radius:8px; background:#fff;
						display:flex; align-items:center; justify-content:center;
					}
					.so-gallery img{ width:100%; height:100%; object-fit:cover; cursor:pointer; }
					.so-gallery .empty{ color:#6b7280; font-style:italic; }
					.so-gallery .src-tag{
						position:absolute; bottom:6px; right:8px; font-size:10px;
						background:rgba(0,0,0,0.5); color:#fff; padding:2px 6px; border-radius:999px;
					}
					.so-gallery .cell{ position:relative; }
				</style>
			`);
		}

		const urls = new Map();
		const is_image = (u) => /\.(png|jpe?g|gif|webp|bmp|svg)$/i.test(u || '');

		const atts = frm.attachments?.get_attachments?.() || [];
		for (const f of atts) {
			if (f.file_url && is_image(f.file_url)) {
				urls.set(f.file_url, { src: 'Attachment' });
			}
		}

		const rows = frm.doc.items || [];
		const need_item_fetch = new Set();
		for (const r of rows) {
			if (r.image && is_image(r.image)) {
				urls.set(r.image, { src: 'Item Row', from: r.item_code });
			} else if (r.item_code) {
				need_item_fetch.add(r.item_code);
			}
		}

		if (need_item_fetch.size) {
			try {
				const item_codes = Array.from(need_item_fetch);
				const items = await frappe.db.get_list('Item', {
					filters: [['name', 'in', item_codes]],
					fields: ['name', 'image', 'website_image'],
					limit: item_codes.length
				});

				for (const it of items) {
					const candidates = [it.image, it.website_image].filter(u => u && is_image(u));
					for (const u of candidates) {
						if (!urls.has(u)) urls.set(u, { src: 'Item Master', from: it.name });
					}
				}
			} catch (e) {
				console.warn('Fetch Item images failed:', e);
			}
		}

		const list = Array.from(urls.entries());
		if (!list.length) {
			$wrap.append('<div class="so-gallery"><div class="empty">Không có ảnh nào để hiển thị</div></div>');
			return;
		}

		const $gallery = $('<div class="so-gallery"></div>');
		list.forEach(([u, meta]) => {
			const $cell = $('<div class="cell"></div>');
			const $imgWrap = $('<div class="img"></div>');
			const $img = $('<img>', { loading: 'lazy', alt: '' }).attr('src', u);
			const $srcTag = $('<div class="src-tag"></div>').text(meta.src);

			$imgWrap.append($img);
			$cell.append($imgWrap, $srcTag);
			$gallery.append($cell);
		});
		$wrap.append($gallery);

		$wrap.off('click.soimg').on('click.soimg', '.so-gallery img', (e) => {
			const src = e.currentTarget?.getAttribute('src');
			const d = new frappe.ui.Dialog({ title: 'Preview', size: 'large' });
			d.$body.css({ padding: 0 });

			const $imgContainer = $('<div style="max-height:70vh; overflow:auto; background:#000"></div>');
			const $img = $('<img>', { style: 'display:block; max-width:100%; margin:auto;' }).attr('src', src);
			$imgContainer.append($img);

			const $srcText = $('<div style="padding:8px 12px; color:#6b7280; font-size:12px;"></div>').text(src);

			d.$body.append($imgContainer, $srcText);
			d.show();
		});
	}
});
