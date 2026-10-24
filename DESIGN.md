# Retopo workspace design

The user's application shell is the reference: ribbon at North, model/guide
navigation at West, canvas at Center, contextual properties at East, and a South
status bar plus a tabbed bottom dock. See WORKSPACE_LAYOUT.md.

Light is the default. Primary actions use blue #2463cf; surfaces use white,
#f8fafc and #f4f6f9; borders use #dce2ea; text uses #253247 and secondary
text #68788e. Gold #b5882c accents active tab underlines and panel symbols;
#fff7e5 is reserved for restrained gold-tinted notices. These are CSS tokens in
index.css, not values to repeat throughout components.

Tool icons are flat inline SVGs, usually 18–23 px with a 1.6 px stroke, no icon
shadows and no decorative 3D treatment. Controls are compact and have accessible
names and visible keyboard focus. Selected states derive from accepted application
state. Generate stays visibly blue; secondary operations use thin gray borders
or transparent backgrounds.

Depth is sparse: one faint ribbon-body gradient, a small ribbon/notice shadow,
and a stronger shadow only for modal dialogs or compact-screen drawers. Panels
use borders and white/gray separation rather than individual card shadows.
This replaces the inherited no-shadow reporting-page convention at the user's
explicit request for subtle gradients and shadows in this workspace.

The font is Segoe UI / system UI. The default size is 13 px, with 10–12 px labels
and metadata. Use actual space for the canvas; avoid large decorative headings
and repeated toolbars. The ribbon scrolls horizontally when necessary. Compact
widths use explicit side drawers, leaving the canvas available.

The optional dark theme uses the same layout, icons and semantics with blue and
gold adapted for contrast. Introducing the shell migrates the previous theme
preference once to the requested light default without changing guide data.
Subsequent explicit theme choices persist normally.

Source appearance is independent of the shell: the imported toilet stays white,
smooth and nonmetallic in both themes. Guide previews, role handles and measured
results remain aligned through panel changes.
