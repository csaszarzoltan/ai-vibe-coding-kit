# AI Vibe Coding Kit - Fejlesztési szabályok

## Követendő szabályok minden módosításnál:

1. **Mindig először teszteket készíts**
   - Új funkció előtt írj tesztet
   - A tesztek elsőként futnak le

2. **Bug javítás szabálya**
   - Bug felfedezése → először reprodukáló teszt
   - Csak ezután javítsd a hibát
   - Futasd le a tesztet, hogy igazold a javítást

3. **Fejlesztés befejezése**
   - Csak akkor fejezd be, ha minden teszt zöld
   - Ne hagyd egy fél beavatkozást

4. **Egyediség**
   - Egy funkciót csak egyszer fejlessz le
   - Kerüld a duplikálást

5. **Dokumentáció frissítése**
   - Minden fejlesztés után frissítsd a dokumentumokat
   - Fejlesztési és felhasználói dokumentációkat tartandó naprakészen

## Projekt struktúra:

```
src/ai_vibe_coding_kit/ - Fő forráskód
tests/ - Teljes test suite
docs/ - Dokumentáció
examples/ - Működő példák
```

## Munka sorrendje:
1. Olvasd el ezt a dokumentumot
2. Írj teszteket a következő funkcióhoz/ javításhoz
3. Implementáld a funkciót/javítást
4. Futtasd a teszteket: `pytest`
5. Ha a tesztek zöldek, a fejlesztő commitolja a kódot
6. A **release-manager** felelős a `main` branchre történő pusholásért a kanban folyamatban, a tesztek sikeres lefutása után
7. A push sikeres után a release-manager frissíti a verziót és a change log-ot, ha szükséges

## Szerepkörök a folyamatban:
- **Fejlesztő**: kód, tesztek, commit
- **Tester/Pre-tester**: tesztek lefuttatása, validálás
- **Release manager**: push, release notes, verziókezelés

## Kötelező befejező lépés a release manager részéről
1. `git status` és `git diff` ellenőrzése.
2. Ha a tesztek zöldek, `git push origin main` a `main` branchre.
3. Ha van verzióemelés, frissítsd a tag-et is.
4. Frissítsd a `CHANGELOG.md`-t és a dokumentációt.
