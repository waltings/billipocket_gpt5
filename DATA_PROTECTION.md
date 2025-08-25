# ⚠️ KRIITILINE ANDMEKAITSE HOIATUS ⚠️

## KASUTAJA ANDMETE KAITSE

**KEELATUD TOIMINGUD TEST-ENGINEER'ILE:**

### 🚫 MIDA MITTE KUNAGI TEHA:
1. **`db.drop_all()`** - KUSTUTAB KOGU ANDMEBAASI!
2. **`db.create_all()`** production andmebaasiga - kirjutab üle kõik andmed!
3. **Andmebaasi faili kustutamine** (`rm billipocket.db`)
4. **Truncate käsud** (`TRUNCATE TABLE clients`)
5. **Mass delete käsud** (`DELETE FROM invoices`)

### ✅ LUBATUD TESTIMISE MEETODID:

#### 1. Kasuta eraldi test andmebaasi:
```python
# Test failis
app.config['DATABASE_URL'] = 'sqlite:///test_database.db'  # MITTE billipocket.db
```

#### 2. Kasuta ajutist in-memory andmebaasi:
```python
app.config['DATABASE_URL'] = 'sqlite:///:memory:'
```

#### 3. Loo backup enne teste:
```bash
cp billipocket.db billipocket_backup_$(date +%Y%m%d_%H%M%S).db
```

### 🔒 KASUTAJA ANDMED ON PÜHA

Kasutaja on loonud järgmised andmed, mida **MITTE KUNAGI** ei tohi kustutada:

#### Kliendid:
- **Hoi Hoi OÜ** (ID: 1)
- **Geopol OÜ** (ID: 2)  
- **HOKA Sports OÜ** (ID: 3)

#### Arved:
- **2025-0001** - Geopol OÜ (798.88€)
- **2025-0002** - Geopol OÜ (1549.01€)
- **2025-0003** - Hoi Hoi OÜ (868.00€)
- **2025-0004** - HOKA Sports OÜ (1314.40€)

### 📋 OHUTUD TESTID

```python
# ✅ ÕIGE viis testida
def test_safely():
    # Kasuta test-spetsiifilist andmebaasi
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///test_temp.db'
    
    with app.app_context():
        db.create_all()  # OK, sest kasutab test DB
        # ... testid ...
        db.drop_all()    # OK, sest kustutab ainult test DB

# ❌ VALE viis testida  
def test_destructively():
    with app.app_context():
        db.drop_all()    # KUSTUTAB KASUTAJA ANDMED!
        db.create_all()  # KUSTUTAB KASUTAJA ANDMED!
```

### 🛡️ AUTOMAATNE KAITSE

See fail teenib hoiatusena. Kui test-engineer kustutab taas andmeid:
1. Backup failid on kättesaadavad `instance/` kaustas
2. Taastamise skript on olemas
3. Logi failid sisaldavad andmete ajalugu

### 📞 VIGA JUHTUB?

Kui andmed on kadunud:
1. **STOP PANIIKAS**
2. Kontrolli backup faile: `ls -la instance/*.db*`
3. Kasuta taastamise skripti
4. Raporteeri test-engineer'ile RANGE viga

---

**MEELDETULETUS: Kasutaja andmed on PÜHA ja ASENDAMATU!**