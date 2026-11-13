package br.com.caracore.pdv.sms;

import androidx.biometric.BiometricManager;
import androidx.biometric.BiometricPrompt;
import androidx.core.content.ContextCompat;
import androidx.fragment.app.FragmentActivity;

import java.util.concurrent.Executor;

/**
 * Confirmação pelo dono do celular antes de revelar a senha do Wi‑Fi ou aprovar
 * uma operação do PDV. Usa digital/rosto quando o aparelho permite e cai para a
 * senha/PIN do celular quando não permite.
 */
public final class DeviceAuth {

    public interface Callback {
        void onSuccess(String metodo);

        void onCancelado();
    }

    private DeviceAuth() {
    }

    public static void confirmar(final FragmentActivity activity, String titulo, String subtitulo,
                                 final Callback callback) {
        BiometricManager gerenciador = BiometricManager.from(activity);
        int disponivel = gerenciador.canAuthenticate(
                BiometricManager.Authenticators.BIOMETRIC_WEAK
                        | BiometricManager.Authenticators.DEVICE_CREDENTIAL);
        if (disponivel != BiometricManager.BIOMETRIC_SUCCESS) {
            callback.onCancelado();
            return;
        }
        Executor executor = ContextCompat.getMainExecutor(activity);
        BiometricPrompt prompt = new BiometricPrompt(activity, executor,
                new BiometricPrompt.AuthenticationCallback() {
                    @Override
                    @android.annotation.SuppressLint("WrongConstant")
                    public void onAuthenticationSucceeded(BiometricPrompt.AuthenticationResult result) {
                        String metodo = "biometria";
                        if (android.os.Build.VERSION.SDK_INT >= 30
                                && result.getAuthenticationType()
                                == android.hardware.biometrics.BiometricPrompt
                                .AUTHENTICATION_RESULT_TYPE_DEVICE_CREDENTIAL) {
                            metodo = "PIN do aparelho";
                        }
                        callback.onSuccess(metodo);
                    }

                    @Override
                    public void onAuthenticationError(int errorCode, CharSequence errString) {
                        callback.onCancelado();
                    }
                });
        BiometricPrompt.PromptInfo info = new BiometricPrompt.PromptInfo.Builder()
                .setTitle(titulo)
                .setSubtitle(subtitulo)
                .setAllowedAuthenticators(BiometricManager.Authenticators.BIOMETRIC_WEAK
                        | BiometricManager.Authenticators.DEVICE_CREDENTIAL)
                .build();
        prompt.authenticate(info);
    }
}
