# 🤖 AGENT INSTRUCTIONS - MUST READ!

## 🚨 ENNE IGA TEMPLATE MUUTMIST

**1. LUE ROUTE KOOD:**
```bash
grep -rn "render_template.*template_name" app/routes/
```

**2. MÄRGI ÜLES MUUTUJAD:**
- Millised muutujad route edastab?
- Millised nimed kasutatakse?

**3. KASUTA AINULT ROUTE MUUTUJAID:**
```html
<!-- ✅ ÕIGE -->
{{ settings.company_name }}  <!-- kui route edastab 'settings' -->

<!-- ❌ VALE -->  
{{ company.company_name }}   <!-- kui route ei edasta 'company' -->
```

## 📋 KIIRE CHECKLIST

- [ ] Lugesin route koodi
- [ ] Tean kõiki template muutujaid  
- [ ] Kasutan conditional rendering'ut
- [ ] Ei kasuta undefined muutujaid
- [ ] Testin enne commit'i

## 🔗 TÄIELIKUD JUHISED

- **Põhjalik juhend:** `CLAUDE.md`
- **Checklist:** `TEMPLATE_VALIDATION_CHECKLIST.md`

## ⚠️ MEELDETULETUS

**IGA 500 INTERNAL SERVER ERROR TÄHENDAB:**
- Agent ei lugenud route koodi
- Kasutas undefined muutujaid template'is
- Ei järginud neid juhiseid

## 🚀 TEMPLATE TESTIMISE PROTOKOLL

**Enne commit'i alati testi:**
```bash
# 1. Kontrolli web template'i
curl -s -w "%{http_code}" http://127.0.0.1:5010/template_route

# 2. Kontrolli template valikuid
curl -s http://127.0.0.1:5010/invoices/new | grep -i "template_name"

# 3. Kontrolli PDF template'i olemasolu
ls -la templates/pdf/invoice_*.html

# 4. Testi PDF genereerimine (valikuline)
curl -X POST http://127.0.0.1:5010/invoices/1/pdf -d "template=minimal"
```

**UUENDATUD TEMPLATE'ID 2025:**
- ✅ `invoice_standard.html` - Standard
- ✅ `invoice_modern.html` - Moodne  
- ✅ `invoice_elegant.html` - Elegantne
- ✅ `invoice_minimal.html` - Minimaalne (**UUS!**)

**JÄRGI ALATI NEID REEGLEID!**