# Template Valideerimise Kontrollnimekiri

## 🔍 ENNE TEMPLATE MUUTMIST

### 1. Route Analüüs
```bash
# Leia route, mis renderib template'i
grep -rn "render_template.*$(basename template_name)" app/routes/

# Vaata route koodi ja märgi üles kõik edastatud muutujad
```

**Kontrollnimekiri:**
- [ ] Leidsin õige route'i
- [ ] Märkisin üles kõik `render_template()` muutujad
- [ ] Mõistan, mis tüüpi andmeid iga muutuja sisaldab

### 2. Olemasolev Template Analüüs
```bash
# Vaata praegused muutujad template'is
grep -n "{{.*}}\|{%.*%}" templates/template_name.html
```

**Kontrollnimekiri:**
- [ ] Vaatasin kõik olemasolevad muutujad
- [ ] Kontrollisin, et need kattuvad route muutujatega
- [ ] Märkisin üles kõik conditional blockid

## ✅ TEMPLATE MUUTMISE AJAL

### 3. Muutujate Kasutamine
```html
<!-- ALATI kontrolli muutuja olemasolu -->
{% if muutuja %}
  {{ muutuja.field }}
{% else %}
  Vaikeväärtus
{% endif %}

<!-- VÕI kasuta default filtrit -->
{{ muutuja.field|default('Vaikeväärtus') }}
```

**Kontrollnimekiri:**
- [ ] Iga uus muutuja on route'is defineeritud
- [ ] Kasutan conditional rendering'ut
- [ ] Kasutan safe property access'i
- [ ] Pole hardcoded väärtusi, mis peaksid olema muutujad

### 4. Dokumentatsiooni vs Aktiivse Koodi Eristamine
```html
<!-- DOKUMENTATSIOON: escaped HTML -->
<code>&#123;&#123; company.name &#125;&#125;</code>

<!-- AKTIIVNE KOOD: käivitatav template -->
{{ settings.company_name }}
```

**Kontrollnimekiri:**
- [ ] Dokumentatsioonis kasutan HTML escape'i
- [ ] Aktiivsesse koodi kasutan ainult route'is defineeritud muutujaid
- [ ] Eraldan selgelt dokumentatsiooni ja aktiivse koodi

## 🧪 ENNE COMMIT'I

### 5. Template Testimine
```bash
# Käivita server
python app.py

# Testi template'i
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:5010/route_path
```

**Kontrollnimekiri:**
- [ ] Server käivitub vigadeta
- [ ] Route tagastab 200 (mitte 500)
- [ ] Leht laadib korrektselt brauseri'is
- [ ] Kõik andmed kuvatakse õigesti
- [ ] Pole JavaScript console'i vigu

### 6. Error Handling Test
```html
<!-- Testi äärmuslikke juhtumeid -->
{% if not data or data|length == 0 %}
  <p>Andmed puuduvad</p>
{% endif %}

<!-- PDF template'ite error handling -->
{% if company.company_logo_url %}
  <img src="{{ company.company_logo_url }}" alt="Logo" />
{% endif %}

{% if company.default_penalty_rate_obj %}
  Viivis: {{ company.default_penalty_rate_obj.rate_per_day }}% päevas
{% else %}
  Viivis: 0% päevas
{% endif %}

<!-- Web template'ite error handling -->
{% if settings.default_penalty_rate_obj %}
  {{ settings.default_penalty_rate_obj.name }}
{% else %}
  Viivis määramata
{% endif %}
```

**Uuendatud Kontrollnimekiri:**
- [ ] Testin tühja/None väärtustega
- [ ] Testin puuduvate andmetega  
- [ ] Kontrollin kõik võimalikud error stsenaariumid
- [ ] **PDF template'ites**: Testin `company.*` muutujaid
- [ ] **Web template'ites**: Testin `settings.*` muutujaid
- [ ] Kontrollin logo olemasolu conditional rendering'uga
- [ ] Testin penalty rate objekti olemasolu

## 🚨 VIGA ILMNEMISEL

### 7. Debug Protokoll
```html
<!-- Lisa ajutine debug info -->
<pre style="background: #f0f0f0; padding: 10px;">
DEBUG INFO:
Available variables: 
{% for key, value in locals().items() %}
  {{ key }}: {{ value|string|truncate(50) }}
{% endfor %}
</pre>
```

**Debug sammud:**
1. [ ] Lisa debug info template'i
2. [ ] Vaata Flask error log'i
3. [ ] Kontrolli route muutujaid
4. [ ] Võrdle template ootustega
5. [ ] Paranda ja testi uuesti

### 8. Levinud Vead ja Lahendused

| Viga | Põhjus | Lahendus |
|------|---------|----------|
| `UndefinedError: 'company' is undefined` | Muutuja pole route'is edastatud | Lisa muutuja route'i või kasuta teist nime |
| `AttributeError: 'NoneType' has no attribute` | Property tagastab None | Lisa `{% if obj %}` kontroll |
| `KeyError` | Dictionary key puudub | Kasuta `get()` meetodit või default filtrit |
| `Template syntax error` | Vale Jinja2 süntaks | Kontrolli `{{}}` ja `{%%}` süntaksit |

## 📋 TEMPLATE REEGLID AGENTIDE JAOKS

### Frontend-Designer Agent:
- [ ] **ALATI** loe route kood enne template muutmist
- [ ] **KUNAGI** ära lisa template koodi dokumentatsioonidesse ilma escape'imata
- [ ] **KASUTA** conditional rendering'ut kõikjal

### Integration-Specialist Agent:
- [ ] **VALIDEERI** route ja template muutujate vastavus
- [ ] **TESTI** kõik form integration'id
- [ ] **KONTROLLI** JavaScript ja backend integration'i

### Backend-Developer Agent:
- [ ] **EDASTA** kõik vajalikud muutujad template'ile  
- [ ] **DOKUMENTEERI** template muutujad route kommentaarides
- [ ] **KASUTA** ühtset nimetamise konventsiooni

## ⚡ KIIRE KONTROLL

**5 sammu iga template muutmise ees:**

1. **Route check**: `grep -n "render_template.*$(template_name)" app/routes/*.py`
2. **Variable check**: Märgi üles kõik route muutujad  
3. **Template check**: Kasuta ainult route muutujaid
4. **Conditional check**: Lisa `{% if %}` kontrollid
5. **Test check**: Testi enne commit'i

## 📖 NÄITED

### ✅ HELLE PRAKTIKA
```python
# Route
@app.route('/settings')
def settings():
    company_settings = CompanySettings.get_settings()
    vat_rates = VatRate.get_active_rates()
    
    return render_template('settings.html',
                          settings=company_settings,  # Template kasutab {{ settings.* }}
                          rates=vat_rates,           # Template kasutab {{ rates }}
                          page_title="Seaded")       # Template kasutab {{ page_title }}
```

```html
<!-- Template -->
<h1>{{ page_title }}</h1>
<p>{{ settings.company_name }}</p>
{% for rate in rates %}
  <option value="{{ rate.id }}">{{ rate.name }}</option>
{% endfor %}
```

### ❌ HALVAD PRAKTIKA
```python
# Route
return render_template('settings.html',
                      settings=company_settings)  # Ainult 'settings' muutuja
```

```html
<!-- Template -->
<h1>{{ company.company_name }}</h1>  <!-- VIGA: 'company' pole defineeritud -->
<p>{{ settings.company_name }}</p>   <!-- OK -->
```

---

## 📚 TEMPLATE MUUTUJATE REGISTRY

### **Web Template'id:**

| Template | Route | Muutujad |
|----------|-------|----------|
| `settings.html` | `/settings` | `form`, `settings`, `all_vat_rates`, `all_payment_terms`, `all_penalty_rates` |
| `invoice_form.html` | `/invoices/new`, `/invoices/edit` | `form`, `clients`, `vat_rates` |
| `invoice_detail.html` | `/invoices/<id>` | `invoice`, `client` |
| `overview.html` | `/` | `metrics`, `recent_invoices` |

### **PDF Template'id:**

| PDF Template | Kasutamise koht | Muutujad |
|--------------|----------------|----------|
| `invoice_standard.html` | PDF genereerimine | `company`, `invoice`, `client`, `today` |
| `invoice_modern.html` | PDF genereerimine | `company`, `invoice`, `client`, `today` |  
| `invoice_elegant.html` | PDF genereerimine | `company`, `invoice`, `client`, `today` |
| `invoice_minimal.html` | PDF genereerimine | `company`, `invoice`, `client`, `today` |

**⚠️ TÄHTIS:** PDF template'ites kasuta `company.*` muutujaid, web template'ites kasuta `settings.*` muutujaid!

## 🔄 UUENDATUD TEMPLATE TESTIMINE

### Minimal Template Testimine:
```bash
# Testi PDF genereerimist
curl -X POST http://127.0.0.1:5010/invoices/1/pdf \
     -d "template=minimal" \
     -H "Content-Type: application/x-www-form-urlencoded"

# Kontrolli template valiku olemasolu arve vormil
curl -s http://127.0.0.1:5010/invoices/new | grep -i "minimal"
```

### Route Analüüs Uuendus:
```bash
# Kontrolli PDF template valikuid
grep -rn "pdf_template.*choices" app/forms.py

# Kontrolli PDF genereerimine routes
grep -rn "invoice_.*\.html" app/routes/pdf.py

# Kontrolli template failide olemasolu
ls -la templates/pdf/invoice_*.html
```

---

**💡 Märkus:** Järgi seda kontrollnimekirja iga template muutmise puhul, et vältida 500 INTERNAL SERVER ERROR'eid!