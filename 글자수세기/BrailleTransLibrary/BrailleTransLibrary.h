#ifndef _BRAILLE_TRANS_LIBRARY_H_
#define _BRAILLE_TRANS_LIBRARY_H_

#ifndef DLLEXPORT
#ifdef __cplusplus
#define DLLEXPORT	extern "C" __declspec(dllexport)
#else
#define DLLEXPORT	__declspec(dllexport)
#endif
#endif

#ifndef DLLIMPORT
#ifdef __cplusplus
#define DLLIMPORT	extern "C" __declspec(dllimport)
#else
#define DLLIMPORT	__declspec(dllimport)
#endif
#endif

DLLEXPORT int BrailleTransStringToBraille(LPTSTR sInput, BYTE* szOutput, int nOutputSize);

DLLEXPORT int BrailleTransStringToBrailleWithOption(LPTSTR sInput, BYTE* szOutput, int nOutputSize, int nGradeMode, int nKoreanRuleVersion);

DLLEXPORT int BrailleTransBrailleToUnicodeBraille(BYTE* szOutput, LPTSTR sInput, int nOutputSize);

DLLEXPORT int BrailleTransBrailleToString(BYTE* sInput, TCHAR* szOutput, int nOutputSize, int languageMode);

#endif
