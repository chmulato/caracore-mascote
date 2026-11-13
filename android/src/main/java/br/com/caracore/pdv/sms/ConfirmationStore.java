package br.com.caracore.pdv.sms;

import android.content.Context;
import android.content.SharedPreferences;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.List;

/**
 * Fila dos pedidos de confirmação e histórico das decisões.
 * Fica no próprio celular: nada depende de internet para decidir.
 */
public final class ConfirmationStore {

    private static final String PREFS = "pdv_confirm_prefs";
    private static final String KEY_PENDENTES = "pendentes";
    private static final String KEY_HISTORICO = "historico";
    private static final int MAX_PENDENTES = 20;
    private static final int MAX_HISTORICO = 100;

    private ConfirmationStore() {
    }

    private static synchronized SharedPreferences prefs(Context context) {
        return context.getApplicationContext().getSharedPreferences(PREFS, Context.MODE_PRIVATE);
    }

    private static JSONArray lerArray(SharedPreferences p, String chave) {
        try {
            return new JSONArray(p.getString(chave, "[]"));
        } catch (JSONException e) {
            return new JSONArray();
        }
    }

    public static synchronized boolean conhecido(Context context, String id) {
        return buscar(prefs(context), id) != null;
    }

    private static JSONObject buscar(SharedPreferences p, String id) {
        JSONArray pendentes = lerArray(p, KEY_PENDENTES);
        for (int i = 0; i < pendentes.length(); i++) {
            JSONObject o = pendentes.optJSONObject(i);
            if (o != null && id.equals(o.optString("id"))) return o;
        }
        JSONArray historico = lerArray(p, KEY_HISTORICO);
        for (int i = 0; i < historico.length(); i++) {
            JSONObject o = historico.optJSONObject(i);
            if (o != null && id.equals(o.optString("id"))) return o;
        }
        return null;
    }

    private static JSONObject paraJson(ConfirmationRequest r) {
        JSONObject o = new JSONObject();
        try {
            o.put("id", r.id);
            o.put("tipo", r.tipo);
            o.put("referencia", r.referencia);
            o.put("valor", r.valorCentavos);
            o.put("motivo", r.motivo);
            o.put("expira", r.expiraEmMillis);
            o.put("recebido", r.recebidoEmMillis);
            o.put("origem", r.origem);
            o.put("enviado", false);
        } catch (JSONException ignored) {
        }
        return o;
    }

    private static ConfirmationRequest paraPedido(JSONObject o) {
        return new ConfirmationRequest(
                o.optString("id"),
                o.optString("tipo"),
                o.optString("referencia"),
                o.optLong("valor"),
                o.optString("motivo"),
                o.optLong("expira"),
                o.optLong("recebido"),
                o.optString("origem"));
    }

    /** Guarda o pedido; devolve false se o mesmo identificador já foi visto. */
    public static synchronized boolean enfileirar(Context context, ConfirmationRequest pedido) {
        SharedPreferences p = prefs(context);
        if (conhecido(context, pedido.id)) return false;
        JSONArray pendentes = lerArray(p, KEY_PENDENTES);
        JSONArray novo = new JSONArray();
        novo.put(paraJson(pedido));
        int limite = Math.min(pendentes.length(), MAX_PENDENTES - 1);
        for (int i = 0; i < limite; i++) {
            JSONObject o = pendentes.optJSONObject(i);
            if (o != null) novo.put(o);
        }
        p.edit().putString(KEY_PENDENTES, novo.toString()).apply();
        return true;
    }

    public static synchronized ConfirmationRequest pendente(Context context, String id) {
        JSONObject o = buscar(prefs(context), id);
        if (o == null) return null;
        return paraPedido(o);
    }

    public static synchronized List<String> pendentesIds(Context context) {
        JSONArray pendentes = lerArray(prefs(context), KEY_PENDENTES);
        List<String> ids = new ArrayList<>();
        for (int i = 0; i < pendentes.length(); i++) {
            JSONObject o = pendentes.optJSONObject(i);
            if (o != null) ids.add(o.optString("id"));
        }
        return ids;
    }

    public static synchronized boolean marcadoEnviado(Context context, String id) {
        JSONObject o = buscar(prefs(context), id);
        return o != null && o.optBoolean("enviado");
    }

    public static synchronized void marcarEnviado(Context context, String id) {
        SharedPreferences p = prefs(context);
        JSONArray pendentes = lerArray(p, KEY_PENDENTES);
        for (int i = 0; i < pendentes.length(); i++) {
            JSONObject o = pendentes.optJSONObject(i);
            if (o != null && id.equals(o.optString("id"))) {
                try {
                    o.put("enviado", true);
                } catch (JSONException ignored) {
                }
            }
        }
        JSONArray historico = lerArray(p, KEY_HISTORICO);
        for (int i = 0; i < historico.length(); i++) {
            JSONObject o = historico.optJSONObject(i);
            if (o != null && id.equals(o.optString("id"))) {
                try {
                    o.put("enviado", true);
                } catch (JSONException ignored) {
                }
            }
        }
        p.edit()
                .putString(KEY_PENDENTES, pendentes.toString())
                .putString(KEY_HISTORICO, historico.toString())
                .apply();
    }

    /** Decisão decidida que ainda não chegou ao computador. */
    public static final class Envio {
        public final ConfirmationRequest pedido;
        public final String status;
        public final String metodo;

        Envio(ConfirmationRequest pedido, String status, String metodo) {
            this.pedido = pedido;
            this.status = status;
            this.metodo = metodo;
        }
    }

    public static synchronized List<Envio> filaDeEnvio(Context context) {
        JSONArray historico = lerArray(prefs(context), KEY_HISTORICO);
        List<Envio> fila = new ArrayList<>();
        for (int i = 0; i < historico.length(); i++) {
            JSONObject o = historico.optJSONObject(i);
            if (o == null || o.optBoolean("enviado")) continue;
            if ("teste".equals(o.optString("origem"))) continue;
            fila.add(new Envio(paraPedido(o), o.optString("status"), o.optString("metodo")));
        }
        return fila;
    }

    /** Fecha o pedido: sai da fila e entra no histórico com a decisão. */
    public static synchronized void decidir(Context context, String id, String status, String metodo) {
        SharedPreferences p = prefs(context);
        JSONArray pendentes = lerArray(p, KEY_PENDENTES);
        JSONObject alvo = null;
        JSONArray restantes = new JSONArray();
        for (int i = 0; i < pendentes.length(); i++) {
            JSONObject o = pendentes.optJSONObject(i);
            if (o != null && id.equals(o.optString("id"))) {
                alvo = o;
            } else if (o != null) {
                restantes.put(o);
            }
        }
        if (alvo == null) return;
        try {
            alvo.put("status", status);
            alvo.put("metodo", metodo);
            alvo.put("decididoEm", System.currentTimeMillis());
        } catch (JSONException ignored) {
        }
        JSONArray historico = lerArray(p, KEY_HISTORICO);
        JSONArray novoHistorico = new JSONArray();
        novoHistorico.put(alvo);
        int limite = Math.min(historico.length(), MAX_HISTORICO - 1);
        for (int i = 0; i < limite; i++) {
            JSONObject o = historico.optJSONObject(i);
            if (o != null) novoHistorico.put(o);
        }
        p.edit()
                .putString(KEY_PENDENTES, restantes.toString())
                .putString(KEY_HISTORICO, novoHistorico.toString())
                .apply();
    }

    /** Linhas prontas para a tela de histórico, da mais recente para a mais antiga. */
    public static synchronized List<String> historicoFormatado(Context context) {
        JSONArray historico = lerArray(prefs(context), KEY_HISTORICO);
        List<String> linhas = new ArrayList<>();
        for (int i = 0; i < historico.length(); i++) {
            JSONObject o = historico.optJSONObject(i);
            if (o == null) continue;
            ConfirmationRequest pedido = paraPedido(o);
            String status = o.optString("status", "?");
            String metodo = o.optString("metodo", "");
            String quando = android.text.format.DateFormat.format("dd/MM HH:mm",
                    new java.util.Date(o.optLong("decididoEm", System.currentTimeMillis()))).toString();
            linhas.add(quando + " — " + pedido.tituloTipo() + " " + pedido.valorFormatado()
                    + " (" + pedido.referencia + "): " + status
                    + (metodo.isEmpty() ? "" : " via " + metodo));
        }
        return linhas;
    }
}
