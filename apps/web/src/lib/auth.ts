import Cookies from "js-cookie";

export const setToken = (token: string) => {
  Cookies.set("token", token, {
    expires: 7,
    sameSite: "strict",
    // secure: true must be enabled in production (HTTPS)
    secure: process.env.NODE_ENV === "production",
  });
};

export const getToken = () => Cookies.get("token");

export const removeToken = () => Cookies.remove("token");

export const isAuthenticated = () => !!getToken();
