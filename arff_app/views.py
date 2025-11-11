import io
import base64
from io import BytesIO

import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
from django.shortcuts import render

from .forms import ArffUploadForm


def _fig_to_base64(fig):
    buf = BytesIO()
    fig.tight_layout()
    # Increase dpi to produce higher-resolution images for better display in the browser
    fig.savefig(buf, format='png', bbox_inches='tight', dpi=150)
    buf.seek(0)
    img_b64 = base64.b64encode(buf.read()).decode('utf-8')
    plt.close(fig)
    return img_b64


def _split_dataframe(df, seed=42):
    n = len(df)
    rng = pd.np.random.default_rng(seed) if hasattr(pd, 'np') else __import__('numpy').random.default_rng(seed)
    indices = pd.np.arange(n) if hasattr(pd, 'np') else __import__('numpy').arange(n)
    rng.shuffle(indices)
    t1 = int(0.6 * n)
    t2 = int(0.8 * n)
    train_idx = indices[:t1]
    val_idx = indices[t1:t2]
    test_idx = indices[t2:]
    return df.iloc[train_idx].reset_index(drop=True), df.iloc[val_idx].reset_index(drop=True), df.iloc[test_idx].reset_index(drop=True)


def _stratified_split(df, label_col, seed=42, ratios=(0.6, 0.2, 0.2)):
    import numpy as np
    assert abs(sum(ratios) - 1.0) < 1e-6, "Las proporciones deben sumar 1.0"
    rng = np.random.default_rng(seed)

    train_parts, val_parts, test_parts = [], [], []
    for label, group in df.groupby(label_col, dropna=False):
        n = len(group)
        idx = np.arange(n)
        rng.shuffle(idx)

        n_train = int(ratios[0] * n)
        n_val = int(ratios[1] * n)
        n_test = n - n_train - n_val

        train_parts.append(group.iloc[idx[:n_train]])
        val_parts.append(group.iloc[idx[n_train:n_train + n_val]])
        test_parts.append(group.iloc[idx[n_train + n_val:]])

    train_df = pd.concat(train_parts, axis=0).sample(frac=1.0, random_state=seed).reset_index(drop=True)
    val_df = pd.concat(val_parts, axis=0).sample(frac=1.0, random_state=seed).reset_index(drop=True)
    test_df = pd.concat(test_parts, axis=0).sample(frac=1.0, random_state=seed).reset_index(drop=True)
    return train_df, val_df, test_df


def _plot_protocol_histogram(series, title, order=None):
    vc = series.astype(str).value_counts()
    if order:
        present = [c for c in order if c in vc.index]
        others = [c for c in vc.index if c not in present]
        ordered = present + others
    else:
        ordered = list(vc.index)
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.bar(ordered, vc.loc[ordered].values)
    ax.set_title(title)
    ax.set_ylabel('Frecuencia')
    ax.set_xlabel('protocol_type')
    return _fig_to_base64(fig)


def _plot_protocol_pair(series, title, order=None, thumb_size=(6, 4), full_size=(14, 10)):
    """Return a dict with thumbnail and full-size base64 images for a series."""
    # thumbnail
    vc = series.astype(str).value_counts()
    if order:
        present = [c for c in order if c in vc.index]
        others = [c for c in vc.index if c not in present]
        ordered = present + others
    else:
        ordered = list(vc.index)

    # thumb
    fig1, ax1 = plt.subplots(figsize=thumb_size)
    ax1.bar(ordered, vc.loc[ordered].values)
    ax1.set_title(title)
    ax1.set_ylabel('Frecuencia')
    ax1.set_xlabel('protocol_type')
    thumb_b64 = _fig_to_base64(fig1)

    # full
    fig2, ax2 = plt.subplots(figsize=full_size)
    ax2.bar(ordered, vc.loc[ordered].values)
    ax2.set_title(title)
    ax2.set_ylabel('Frecuencia')
    ax2.set_xlabel('protocol_type')
    full_b64 = _fig_to_base64(fig2)

    return {'thumb': thumb_b64, 'full': full_b64}


def analyze_arff(request):
    context = {'form': ArffUploadForm()}

    if request.method == 'POST':
        form = ArffUploadForm(request.POST, request.FILES)
        if form.is_valid():
            file_content = None
            file_name = None

            # Only local uploads are supported now
            arff_file = request.FILES.get('arff_file')
            if not arff_file:
                context['error'] = 'No se seleccionó ningún archivo.'
                return render(request, 'arff_app/pagina_web.html', context)
            if not arff_file.name.lower().endswith('.arff'):
                context['error'] = 'El archivo debe tener extensión .arff'
                return render(request, 'arff_app/pagina_web.html', context)

            file_name = arff_file.name
            raw = arff_file.read()
            try:
                file_content = raw.decode('utf-8')
            except Exception:
                file_content = raw.decode('latin-1')

            try:
                # Try liac-arff first
                try:
                    import arff as liac_arff
                    data_dict = liac_arff.loads(file_content)
                    attribute_names = [attr[0] for attr in data_dict['attributes']]
                    df = pd.DataFrame(data_dict['data'], columns=attribute_names)
                except Exception:
                    # Fallback: parse with pandas ignoring @attribute lines
                    attribute_names = []
                    for line in file_content.splitlines():
                        if line.strip().lower().startswith('@attribute'):
                            parts = line.split()
                            if len(parts) >= 2:
                                attribute_names.append(parts[1].strip("'\""))

                    df = pd.read_csv(io.StringIO(file_content), comment='@', header=None, na_values=['?'])
                    if len(attribute_names) == len(df.columns):
                        df.columns = attribute_names
                    else:
                        df.columns = [f'Col_{i+1}' for i in range(len(df.columns))]

                # Convert numeric columns (avoid FutureWarning): try conversion and ignore failures
                for c in df.columns:
                    try:
                        df[c] = pd.to_numeric(df[c])
                    except Exception:
                        # keep original if conversion fails
                        pass

                # Prepare the dataframe for display (limit to 1000 rows to avoid huge responses)
                truncated = False
                if len(df) > 1000:
                    truncated = True
                    df_display = df.head(1000).reset_index(drop=True)
                else:
                    df_display = df.copy()

                df_html = df_display.to_html(classes='table table-hover table-striped', border=0, na_rep='-')

                # Create splits on the dataframe to keep processing light
                pt_col = None
                lower_map = {c.lower(): c for c in df_display.columns}
                if 'protocol_type' in lower_map:
                    pt_col = lower_map['protocol_type']

                if pt_col is not None:
                    train_df, val_df, test_df = _stratified_split(df_display, pt_col, seed=42)
                else:
                    train_df, val_df, test_df = _split_dataframe(df_display, seed=42)

                plots = {}
                if pt_col is not None:
                    try:
                        uniques = set(df[pt_col].astype(str).unique())
                        desired_test_order = None
                        if 'tcp' in uniques:
                            base = ['udp', 'tcp', 'icmp']
                            desired_test_order = [c for c in base if c in uniques]

                        plots['prot_full'] = _plot_protocol_pair(df[pt_col], 'protocol_type - Dataset completo', order=None)
                        plots['prot_train'] = _plot_protocol_pair(train_df[pt_col], 'protocol_type - Train', order=None)
                        plots['prot_val'] = _plot_protocol_pair(val_df[pt_col], 'protocol_type - Validación', order=None)
                        plots['prot_test'] = _plot_protocol_pair(test_df[pt_col], 'protocol_type - Test', order=desired_test_order)
                    except Exception:
                        pass
                context.update({
                    'df_html': df_html,
                    'file_name': file_name,
                    'num_rows': df.shape[0],
                    'num_cols': df.shape[1],
                    'plots': plots,
                    'protocol_col': pt_col,
                    'truncated': truncated,
                })
            except Exception as e:
                context['error'] = f'Error al procesar el archivo: {str(e)}'
        else:
            context['error'] = 'Formulario inválido.'

    return render(request, 'arff_app/pagina_web.html', context)
