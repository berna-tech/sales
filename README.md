# Berna Uçar Satış Performans Dashboard

Bu Streamlit uygulaması Excel dosyası yüklenince satış performans dashboard'u oluşturur.

## Lokal çalıştırma

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Streamlit Community Cloud ile yayınlama

1. GitHub'da yeni bir repo aç.
2. Bu klasördeki `app.py`, `requirements.txt` ve `.streamlit/config.toml` dosyalarını repoya yükle.
3. https://share.streamlit.io adresinden GitHub hesabınla giriş yap.
4. New app > repo seç > main file path: `app.py`.
5. Deploy'a bas.
6. Oluşan linki ekibinle paylaş.

## Kullanım

- Sol menüden Excel yükle.
- Kolonlar otomatik eşleşir.
- Gerekirse manuel kolon eşleştirmesini düzelt.
- Dashboard sekmelerinden yönetici özeti, Berna Uçar paneli, ürün/bayi analizi ve öne çıkan satışları incele.

## Desteklenen formatlar

- xlsx
- xls
- xlsb
