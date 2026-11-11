package br.com.caracore.pdv.sms;

import android.content.ContentProvider;
import android.content.ContentValues;
import android.content.UriMatcher;
import android.database.Cursor;
import android.database.MatrixCursor;
import android.net.Uri;
import android.os.Build;
import android.provider.Settings;

/**
 * ContentProvider para o PDV Desktop obter via ADB (content query):
 * - HardwareID do celular (ANDROID_ID)
 * - Chave de licença atual (armazenada via SMS CC-LICENSE)
 * - Se a licença está válida para o mês atual
 *
 * Exemplo de uso no PDV:
 *   adb shell content query --uri content://br.com.caracore.pdv.sms.licenca/licenca
 */
public class LicencaContentProvider extends ContentProvider {

    public static final String AUTHORITY = "br.com.caracore.pdv.sms.licenca";
    public static final Uri CONTENT_URI = Uri.parse("content://" + AUTHORITY + "/licenca");

    public static final String COL_HARDWARE_ID = "hardware_id";
    public static final String COL_CHAVE = "chave";
    public static final String COL_VALIDA = "valida";
    public static final String COL_MES_ANO = "mes_ano";

    private static final int MATCH_LICENCA = 1;
    private UriMatcher matcher;

    @Override
    public boolean onCreate() {
        matcher = new UriMatcher(UriMatcher.NO_MATCH);
        matcher.addURI(AUTHORITY, "licenca", MATCH_LICENCA);
        return true;
    }

    @Override
    public Cursor query(Uri uri, String[] projection, String selection,
                        String[] selectionArgs, String sortOrder) {
        if (matcher.match(uri) != MATCH_LICENCA) {
            return null;
        }
        String hardwareId = obterHardwareId();
        SmsPreferences prefs = new SmsPreferences(getContext());
        String chave = prefs.getChaveLicenca();
        boolean valida = prefs.isLicencaValida();
        String mesAno = extrairMesAno(chave);

        MatrixCursor c = new MatrixCursor(new String[]{COL_HARDWARE_ID, COL_CHAVE, COL_VALIDA, COL_MES_ANO});
        c.addRow(new Object[]{
                hardwareId != null ? hardwareId : "",
                chave != null ? chave : "",
                valida ? 1 : 0,
                mesAno != null ? mesAno : ""
        });
        return c;
    }

    @Override
    public String getType(Uri uri) {
        return null;
    }

    @Override
    public Uri insert(Uri uri, ContentValues values) {
        return null;
    }

    @Override
    public int delete(Uri uri, String selection, String[] selectionArgs) {
        return 0;
    }

    @Override
    public int update(Uri uri, ContentValues values, String selection, String[] selectionArgs) {
        return 0;
    }

    private String obterHardwareId() {
        try {
            return Settings.Secure.getString(getContext().getContentResolver(), Settings.Secure.ANDROID_ID);
        } catch (Exception e) {
            return Build.SERIAL != null ? Build.SERIAL : "unknown";
        }
    }

    private String extrairMesAno(String chave) {
        if (chave == null || chave.isEmpty()) return null;
        java.util.regex.Matcher m = java.util.regex.Pattern.compile("^CC-(\\d{6})-[0-9a-fA-F]{8}$").matcher(chave.trim());
        return m.matches() ? m.group(1) : null;
    }
}
