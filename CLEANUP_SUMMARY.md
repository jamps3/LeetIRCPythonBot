# Code Cleanup Summary

## Legacy Code Identified for Future Cleanup 🔄

### 1. Dual Word Tracking Systems
**Current State**: Two parallel word tracking systems running
- **Legacy System** (lines 845-850): Uses `load()`, `update_kraks()`, `save()`
- **New System** (lines 761-778): Uses `general_words.process_message()`, `drink_tracker.process_message()`

**Commands Still Using Legacy System**:
- `!sana` - word search
- `!topwords` - top words display  
- `!leaderboard` - user activity ranking

### 2. Legacy Drink Detection
**Current State**: Redundant drink word detection
- **Legacy** (lines 779-795): Regex pattern + `count_kraks()` function
- **New** (line 771): `drink_tracker.process_message()` with privacy controls

### 3. Legacy Comments and Code
- **Line 776**: Comment about legacy tamagotchi removal
- **Line 799**: Commented out old IRC response code
- **Lines 1347-1350**: Commented out legacy IPFS parsing code

## Next Steps / TODO 🔮

1. **Migrate Legacy Word Commands**: Update `!sana`, `!topwords`, `!leaderboard` to use new system
2. **Remove Legacy Drink Detection**: Remove redundant regex-based detection
3. **Clean Up Comments**: Remove legacy code comments
4. Verify all eurojackpot commands work correctly
5. Test word tracking commands (`!sana`, `!topwords`, `!leaderboard`)  
6. Test drink tracking commands (`!kraks`, `!drinkword`, `!drink`)
7. Verify tamagotchi commands work properly
8. Test console vs IRC command parity
