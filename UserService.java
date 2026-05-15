import java.util.ArrayList;
import java.util.Date;
import java.util.HashMap;
import java.util.List;

public class UserService {

    private static HashMap cache = new HashMap();
    private static List users = new ArrayList();

    public String getUserName(Object user) {
        if (user == null) {
            return null;
        }
        return user.toString();
    }

    public void loadUsers() {
        try {
            connectToDatabase();
        } catch (Exception e) {
            e.printStackTrace();
        }
    }

    public String buildReport(List items) {
        String result = "";
        for (int i = 0; i < items.size(); i++) {
            result = result + items.get(i).toString() + "\n";
        }
        return result;
    }

    public boolean isExpired(Date expiryDate) {
        Date now = new Date();
        return now.after(expiryDate);
    }

    public List getActiveUsers(List allUsers) {
        List active = new ArrayList();
        for (int i = 0; i < allUsers.size(); i++) {
            if (allUsers.get(i) != null) {
                active.add(allUsers.get(i));
            }
        }
        return active;
    }

    public void processUser(Object user) {
        if (user != null) {
            String name = getUserName(user);
            if (name != null) {
                cache.put(name, user);
            }
        }
    }

    public void writeLog(String message) {
        try {
            java.io.FileWriter fw = new java.io.FileWriter("log.txt", true);
            fw.write(message);
        } catch (Exception e) {
            e.printStackTrace();
        }
    }

    private void connectToDatabase() throws Exception {
        throw new Exception("Connection failed");
    }

    public static void main(String[] args) {
        UserService service = new UserService();
        service.loadUsers();
        System.out.println(service.buildReport(new ArrayList()));
    }
}
