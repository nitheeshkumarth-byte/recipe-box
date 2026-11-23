import React, { useEffect, useRef, useState } from "react";
import { ActivityIndicator, BackHandler, Linking, Pressable, Share, StatusBar, StyleSheet, Text, View } from "react-native";
import { SafeAreaProvider, SafeAreaView } from "react-native-safe-area-context";
import { WebView } from "react-native-webview";

function secureOrigin(value: string | undefined) {
    if (!value) return null;
    try {
        const url = new URL(value);
        return url.protocol === "https:" && !url.username && !url.password ? url.origin : null;
    } catch {
        return null;
    }
}

const origin = secureOrigin(process.env.EXPO_PUBLIC_RECIPE_BOX_URL);
const loginOrigins = (process.env.EXPO_PUBLIC_RECIPE_BOX_SSO_ORIGINS || "")
    .split(",").map((value: string) => secureOrigin(value.trim())).filter(Boolean);

function ToolbarButton({ label, onPress, disabled }: {
    label: string; onPress: () => void; disabled?: boolean;
}) {
    return (
        <Pressable accessibilityRole="button" disabled={disabled} onPress={onPress} style={styles.button}>
            <Text style={[styles.buttonText, disabled && styles.disabled]}>{label}</Text>
        </Pressable>
    );
}

function RecipeBox() {
    const web = useRef<WebView>(null);
    const [canGoBack, setBack] = useState(false);
    const [recipeLink, setRecipeLink] = useState<string | null>(null);
    const [failed, setFailed] = useState(false);
    const [attempt, setAttempt] = useState(0);
    const home = origin ? origin + "/" : null;

    useEffect(() => {
        const back = BackHandler.addEventListener("hardwareBackPress", () => {
            if (!canGoBack || !web.current) return false;
            web.current.goBack();
            return true;
        });
        return () => back.remove();
    }, [canGoBack]);

    function allowNavigation({ url }: { url: string }) {
        const target = secureOrigin(url);
        if (url === "about:blank" || (target && (target === origin || loginOrigins.includes(target)))) return true;
        if (target) Linking.openURL(url).catch(() => {});
        return false;
    }

    function updateLocation({ url, canGoBack: canReturn }: { url: string; canGoBack: boolean }) {
        setBack(canReturn);
        const path = secureOrigin(url) === origin ? new URL(url).pathname : "";
        setRecipeLink(origin && /^\/recipe\/[1-9][0-9]*\/?$/.test(path) ? origin + path : null);
    }

    function retry() {
        setFailed(false);
        setBack(false);
        setRecipeLink(null);
        setAttempt(current => current + 1);
    }

    return (
        <SafeAreaView style={styles.container}>
            <StatusBar barStyle="dark-content" />
            <View style={styles.header}>
                <ToolbarButton label="Back" disabled={!canGoBack} onPress={() => web.current?.goBack()} />
                <Text accessibilityRole="header" style={styles.title}>Recipe Box</Text>
                <ToolbarButton label="Share" disabled={!recipeLink}
                    onPress={() => { if (recipeLink) Share.share({ message: recipeLink }).catch(() => {}); }} />
            </View>
            {!home || failed ? (
                <View style={styles.notice}>
                    <Text style={styles.title}>{home ? "Could not load Recipe Box" : "Recipe Box needs a server URL"}</Text>
                    <Text style={styles.copy}>{home ? "Check your connection and try again." : "Set EXPO_PUBLIC_RECIPE_BOX_URL to your HTTPS deployment."}</Text>
                    {home && <ToolbarButton label="Try again" onPress={retry} />}
                </View>
            ) : (
                <WebView key={attempt} ref={web} source={{ uri: home }}
                    originWhitelist={["https://*", "about:blank"]}
                    onShouldStartLoadWithRequest={allowNavigation}
                    onNavigationStateChange={updateLocation}
                    onError={() => setFailed(true)}
                    onHttpError={({ nativeEvent }) => {
                        if (nativeEvent.url === home && nativeEvent.statusCode >= 500) setFailed(true);
                    }}
                    mixedContentMode="never"
                    allowFileAccess={false}
                    thirdPartyCookiesEnabled={false}
                    setSupportMultipleWindows={false}
                    startInLoadingState
                    renderLoading={() => <ActivityIndicator style={styles.loading} color="#496752" />}
                />
            )}
        </SafeAreaView>
    );
}

export default function App() {
    return <SafeAreaProvider><RecipeBox /></SafeAreaProvider>;
}

const styles = StyleSheet.create({
    container: { flex: 1, backgroundColor: "#f6f4eb" },
    header: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", paddingHorizontal: 8, borderBottomWidth: StyleSheet.hairlineWidth, borderColor: "#d9dfd2" },
    title: { color: "#263129", fontSize: 18, fontWeight: "700", textAlign: "center" },
    button: { minWidth: 54, minHeight: 44, paddingHorizontal: 8, alignItems: "center", justifyContent: "center" },
    buttonText: { color: "#304d3b", fontWeight: "600" },
    disabled: { opacity: 0.35 },
    notice: { flex: 1, justifyContent: "center", alignItems: "center", gap: 14, padding: 24 },
    copy: { color: "#515e52", textAlign: "center" },
    loading: { position: "absolute", top: 0, right: 0, bottom: 0, left: 0 },
});
