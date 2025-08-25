# CLAUDE.md - Flask Template Development Guidelines

## KRIITILISED JINJA2 TEMPLATE REEGLID

### ⚠️ ENNE TEMPLATE MUUTMIST ALATI:

1. **Kontrolli route'i muutujaid**
   ```python
   return render_template('template.html', 
                         muutuja1=väärtus1,
                         muutuja2=väärtus2)
   ```
   - Template'is saad kasutada AINULT neid muutujaid, mis route edastab
   - **MITTE KUNAGI** ära kasuta template'is muutujaid, mida route ei edasta

2. **Loe route kood enne template muutmist**
   ```bash
   # Otsi route'i, mis renderib template'i
   grep -n "render_template.*template_nimi" app/routes/*.py
   ```

3. **Kontrolli olemasolevat template struktuuri**
   ```bash
   # Vaata, millised muutujad on juba kasutuses
   grep -n "{{ \|{%" templates/template_nimi.html
   ```

### 🚫 VÄLTIDA:

1. **UndefinedError põhjused:**
   ```html
   <!-- VALE: route ei edasta 'company' muutujat -->
   {{ company.name }}
   
   <!-- ÕIGE: route edastab 'settings' muutujat -->
   {{ settings.company_name }}
   ```

2. **Template vs Dokumentatsioon segadus:**
   ```html
   <!-- VALE: aktiivselt täidetav template kood dokumentatsioonis -->
   <code>{{ company.name }}</code> - Ettevõtte nimi
   
   <!-- ÕIGE: escaped HTML dokumentatsioonis -->
   <code>&#123;&#123; company.name &#125;&#125;</code> - Ettevõtte nimi
   ```

3. **Property meetodite kasutamine ilma kontrollita:**
   ```html
   <!-- VALE: meetod võib tagastada None -->
   {{ settings.some_property_method.attribute }}
   
   <!-- ÕIGE: kontrolli enne kasutamist -->
   {% if settings.some_property_method %}
     {{ settings.some_property_method.attribute }}
   {% endif %}
   ```

### ✅ TURVALISED PRAKTIKAD:

1. **Template muutujate kontroll:**
   ```python
   # routes.py failis
   def some_view():
       data = get_some_data()
       return render_template('template.html',
                            data=data,  # See on template'is kättesaadav
                            user=current_user)  # See ka
   ```

2. **Conditional rendering:**
   ```html
   {% if data %}
     {{ data.some_field }}
   {% else %}
     Andmed puuduvad
   {% endif %}
   ```

3. **Safe property access:**
   ```html
   {{ data.field|default('Vaikeväärtus') }}
   ```

## FLASK ROUTE & TEMPLATE REEGLID

### Template Edastamine:

```python
# ✅ ÕIGE viis
return render_template('settings.html',
                      form=form,
                      settings=company_settings,  # Template saab kasutada {{ settings.* }}
                      rates=vat_rates)           # Template saab kasutada {{ rates }}

# ❌ VALE - template eeldab 'company' muutujat
return render_template('settings.html',
                      form=form,
                      settings=company_settings)  # Template ei saa kasutada {{ company.* }}
```

### Template Kasutamine:

```html
<!-- ✅ ÕIGE - kasutab route poolt edastatud muutujaid -->
<h1>{{ settings.company_name }}</h1>
<p>{{ form.company_name.label }}</p>

<!-- ❌ VALE - kasutab muutujaid, mida route ei edasta -->
<h1>{{ company.company_name }}</h1>  <!-- UndefinedError! -->
<p>{{ unknown_var }}</p>             <!-- UndefinedError! -->
```

## DOKUMENTATSIOONI TEMPLATES

Kui lood dokumentatsiooni, mis näitab template koodi:

```html
<!-- ✅ ÕIGE viis näidata template koodi -->
<code>&#123;&#123; company.name &#125;&#125;</code>

<!-- ❌ VALE - see proovib koodi käivitada -->
<code>{{ company.name }}</code>
```

## DEBUGGING TEMPLATE VIGADE KORRAL

1. **Kontrolli Flask logs:**
   ```bash
   tail -f logs/billipocket.log
   ```

2. **Liigu template'i ja vaata muutujaid:**
   ```html
   <!-- Ajutine debug info -->
   <pre>{{ settings|pprint }}</pre>
   <pre>Available variables: {{ locals().keys()|list }}</pre>
   ```

3. **Testi route'i eraldi:**
   ```python
   @app.route('/debug-settings')
   def debug_settings():
       # Lisa siia sama loogika nagu päris route'is
       return jsonify({
           'available_vars': list(locals().keys()),
           'settings_exists': 'settings' in locals()
       })
   ```

## AGENT-SPECIFIC REEGLID

### Frontend-Designer Agent:
- **ALATI** kontrolli enne, millised muutujad route edastab
- **ÄRA** lisa template koodi dokumentatsioonidesse ilma escapimata
- **KASUTA** conditional rendering kõikjal kus võimalik

### Integration-Specialist Agent:
- **KONTROLLI** route ja template vastavust
- **VALIDEERI** kõik form fieldid ja nende kasutamine
- **TESTI** template'i enne commit'i

### Backend-Developer Agent:
- **EDASTA** kõik vajalikud muutujad template'ile
- **DOKUMENTEERI** millised muutujad template'ile edastatakse
- **JÄRGI** ühtset nimetamise konventsiooni

## TEMPLATE MUUTUJATE NIMETAMISE KONVENTSIOONID

```python
# ✅ ÕIGE - selged, kirjeldavad nimed
return render_template('template.html',
                      company_settings=settings,
                      vat_rates_list=rates,
                      invoice_form=form)

# ❌ VALE - ebamäärased nimed
return render_template('template.html',
                      data=settings,
                      items=rates,
                      obj=form)
```

## TEMPLATE STRUKTUURI KONTROLL

Enne template'i muutmist:

```bash
# 1. Vaata, mis muutujaid template kasutab
grep -o "{{ [^}]* }}" templates/template.html | sort | uniq

# 2. Vaata, mis muutujaid route edastab  
grep -A 10 "render_template.*template" app/routes/*.py

# 3. Võrdle neid - peavad kattuma!
```

## VIGA VÄLTIMISE CHECKLIST

- [ ] Lugesin route koodi ja tean, millised muutujad edastatakse
- [ ] Kontrollisin, et kõik template muutujad on route'is defineeritud
- [ ] Kasutan conditional rendering kõikjal, kus andmed võivad puududa
- [ ] Dokumentatsioonis kasutan HTML escape'itud template koodi
- [ ] Testisin template'i enne commit'i

## NÄITED TAVALISTEST VIGADEST

### Viga #1: Muutuja puudub
```python
# Route
return render_template('page.html', user=current_user)

# Template
{{ company.name }}  # ❌ VIGA - 'company' pole defineeritud
{{ user.name }}     # ✅ OK
```

### Viga #2: Property tagastab None
```python
# Model
@property 
def some_data(self):
    return None  # Võib tagastada None

# Template  
{{ obj.some_data.field }}     # ❌ VIGA - AttributeError
{% if obj.some_data %}        # ✅ OK
  {{ obj.some_data.field }}
{% endif %}
```

### Viga #3: Dokumentatsioon käivitab koodi
```html
<!-- Dokumentatsiooni sektsioon -->
<p>Kasuta: {{ company.name }}</p>  <!-- ❌ VIGA - proovib käivitada -->
<p>Kasuta: &#123;&#123; company.name &#125;&#125;</p>  <!-- ✅ OK - näitab teksti -->
```

## TEMPLATE TESTIMINE

```python
# Loo test route template testimiseks
@app.route('/test-template')
def test_template():
    return render_template('your_template.html',
                          # Lisa KÕIK vajalikud muutujad
                          settings=test_settings,
                          form=test_form,
                          # jne...
                          )
```

---

## OBLIGATOORSED SAMMUD IGA AGENDI JAOKS

### 🎨 FRONTEND-DESIGNER AGENT
**ENNE template muutmist:**
1. Käivita: `grep -rn "render_template.*template_name" app/routes/`
2. Loe route kood täielikult läbi
3. Märgi üles KÕIK route'is edastatud muutujad
4. Kasuta template'is AINULT neid muutujaid

**Template töö ajal:**
- ✅ Kasuta `{% if muutuja %}{{ muutuja.field }}{% endif %}`
- ✅ Dokumentatsioonis kasuta `&#123;&#123; code &#125;&#125;` 
- ❌ MITTE KUNAGI `{{ undefined_var }}`

### ⚙️ INTEGRATION-SPECIALIST AGENT  
**Template-Route ühilduvuse kontroll:**
1. Võrdle route `render_template()` parameetreid template muutujatega
2. Testi iga form field integratsioon
3. Valideeri JavaScript ja backend koostöö

### 🔧 BACKEND-DEVELOPER AGENT
**Route'ide loomisel:**
1. Edasta template'ile KÕIK vajalikud muutujad
2. Kasuta kirjeldavaid muutujanimesid
3. Dokumenteeri template muutujad route kommentaarides

```python
@app.route('/settings')
def settings():
    # Template muutujad: settings, rates, form
    company_settings = CompanySettings.get_settings()  
    vat_rates = VatRate.get_active_rates()
    form = CompanySettingsForm(obj=company_settings)
    
    return render_template('settings.html',
                          settings=company_settings,    # {{ settings.* }}
                          rates=vat_rates,              # {{ rates }}  
                          form=form)                    # {{ form.* }}
```

## 🚨 TEMPLATE VIGA PROTOKOLL

**Kui näed 500 INTERNAL SERVER ERROR:**

1. **Vaata Flask log'i:**
   ```bash
   tail -f logs/billipocket.log
   ```

2. **Leia UndefinedError põhjus:**
   - Milline muutuja on undefined?
   - Kas see on route'is edastatud?
   - Kas nimetus on õige?

3. **Paranda:**
   ```html
   <!-- VALE -->
   {{ company.name }}
   
   <!-- ÕIGE - kontrolli esmalt route'i -->
   {{ settings.company_name }}  <!-- kui route edastab 'settings' -->
   ```

4. **Testi kohe:**
   ```bash
   curl -s -w "%{http_code}" http://127.0.0.1:5010/template_route
   ```

## 📚 TEMPLATE MUUTUJATE REGISTRY

**Sagedasemad template'id ja nende muutujad:**

### **Web Template'id:**

| Template | Route | Muutujad |
|----------|-------|----------|
| `settings.html` | `/settings` | `form`, `settings`, `all_vat_rates`, `all_payment_terms`, `all_penalty_rates` |
| `invoice_form.html` | `/invoices/new`, `/invoices/edit` | `form`, `clients`, `vat_rates` |
| `invoice_detail.html` | `/invoices/<id>` | `invoice`, `client` |
| `overview.html` | `/` | `metrics`, `recent_invoices` |

### **PDF Template'id:**

| Template | Route | Muutujad |
|----------|-------|----------|
| `invoice_standard.html` | PDF genereerimine | `company`, `invoice`, `client`, `today` |
| `invoice_modern.html` | PDF genereerimine | `company`, `invoice`, `client`, `today` |
| `invoice_elegant.html` | PDF genereerimine | `company`, `invoice`, `client`, `today` |
| `invoice_minimal.html` | PDF genereerimine | `company`, `invoice`, `client`, `today` |

**⚠️ KRIITILINE VAHE:**
- **Web template'ites:** Kasuta `{{ settings.company_name }}`
- **PDF template'ites:** Kasuta `{{ company.company_name }}`

**ALATI kontrolli route koodi, et saada täpne nimekiri!**

## 🛡️ VEATEKSTIDE TEMPLATE SÕNUM

Template vigade korral näidatakse kasutajale:
```html
<!-- 500.html template -->
<h1>Süsteemi viga</h1>
<p>Template rendering ebaõnnestus. Kontrolli CLAUDE.md juhiseid.</p>
```

---

**⚠️ KRIITILINE: Iga 500 error tähendab, et agent ei järginud neid juhiseid. 
Loe TEMPLATE_VALIDATION_CHECKLIST.md enne igat template muutmist!**

**MEELDETULETUS: Iga template viga põhjustab 500 INTERNAL SERVER ERROR. Järgi neid reegleid hoolikalt!**